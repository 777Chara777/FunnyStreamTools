import os
import inspect
import logging
import importlib
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.eventbus import bus
from app.baseprovider import BaseProvider
from app.baseplugin import BasePlugin

IS_DEBUG = not True
logging.basicConfig(level=logging.DEBUG if IS_DEBUG else logging.INFO)
logger = logging.getLogger("FunnyStreamTools")

app = FastAPI(title="FunnyStreamTools")

class FunnyStreamTools:
    def __init__(self, fastapi_app):
        self.app = fastapi_app
        self.widgets = {}
        self.providers = {}
        self.background_tasks = []

    def load_all(self):
        base_dir = os.path.dirname(__file__)
        self._discover("providers", BaseProvider, self.providers)
        self._discover("plugins", BasePlugin, self.widgets)

    def _discover(self, directory: str, base_class, registry: dict):
        """Universal directory scanner using inspect"""
        if not os.path.exists(directory): return

        is_provider = issubclass(base_class, BaseProvider)
        layer_name = "providers" if is_provider else "plugins"

        for entry in os.scandir(directory):
            if entry.is_dir():
                name = entry.name
                try:
                    module = importlib.import_module(f"{layer_name}.{name}.main")
                    for _, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, base_class) and obj is not base_class:
                            
                            # Instance creation settings
                            if is_provider:
                                instance = obj(provider_id=name, bus=bus)
                            else:
                                # Immediately subscribe the widget to the required provider topic
                                instance = obj(
                                    name=name, 
                                    prefix=f"/widget/{name}", 
                                    bus=bus,
                                    subscribed_topics=None # Can be moved to the plugin configuration
                                )
                                self.app.include_router(instance.router)
                            
                            registry[name] = instance
                            print(f"[+] [{layer_name.upper()}] Init class {obj.__name__}")
                except Exception as e:
                    print(f"[-] Error loading layer {layer_name} ({name}): {e}")
                    if IS_DEBUG: raise

    async def start_providers(self):
        for p_id, provider in self.providers.items():
            print(f"[*] Starting a background process for the provider: {p_id}")
            task = asyncio.create_task(provider.start())
            self.background_tasks.append(task)

    def stop_providers(self):
        for provider in self.providers.values():
            provider.running = False
        for task in self.background_tasks:
            task.cancel()

engine = FunnyStreamTools(app)
engine.load_all()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await engine.start_providers()
    yield
    engine.stop_providers()

app.router.lifespan_context = lifespan