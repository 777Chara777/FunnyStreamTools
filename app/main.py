import os
import sys
import json
import inspect
import logging
import importlib
import asyncio

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.eventbus import bus
from app.baseprovider import BaseProvider
from app.baseplugin import BasePlugin

IS_DEBUG = not getattr(sys, 'frozen', False)
BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if getattr(sys, 'frozen', False):
    local_venv = os.path.join(BASE_DIR, ".venv", "Lib", "site-packages")
    if os.path.exists(local_venv):
        sys.path.insert(0, local_venv)

logging.basicConfig(level=logging.DEBUG if IS_DEBUG else logging.INFO)
logger = logging.getLogger("FunnyStreamTools")

app = FastAPI(title="FunnyStreamTools")

class FunnyStreamTools:
    def __init__(self, fastapi_app):
        self.app = fastapi_app
        self.widgets = {}
        self.providers = {}
        self.background_tasks = []
        self.config = self._load_config()

        self.plugin_providers_map = {}

    def _load_config(self) -> dict:
        config_path = os.path.join(BASE_DIR, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"providers": {}, "plugins": {}}

    def save_current_config_to_file(self):
        """Helper method for saving the current self.config to disk"""
        with open(os.path.join(BASE_DIR, "config.json"), "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def update_and_save_config(self, new_config: dict):
        """Updates the configuration in memory and saves it to disk."""
        self.config = new_config
        
        plugins_config = new_config.get("plugins", {})
        for name, plugin_instance in self.widgets.items():
            if name in plugins_config:
                plugin_instance.current_theme = plugins_config[name].get("current_theme", "index.html")
                
        providers_config = new_config.get("providers", {})
        for name, provider_instance in self.providers.items():
            if name in providers_config:
                provider_instance.running = providers_config[name].get("enabled", True)

        with open(os.path.join(BASE_DIR, "config.json"), "w", encoding="utf-8") as f:
            import json
            json.dump(new_config, f, indent=2, ensure_ascii=False)

    async def reload_modules(self):
        """Full directory rescan, disabling old modules, and adding new ones."""
        self.config = self._load_config()
        
        self.stop_providers()
        self.providers.clear()
        self.background_tasks.clear()

        self.app.router.routes = [
            route for route in self.app.router.routes 
            if not (hasattr(route, "path") and route.path.startswith("/widget/"))
        ]
        self.widgets.clear()

        self.load_all()
        
        await self.start_providers()
        print("[*] All modules have been successfully re-read from the disk!")


    def load_all(self):
        self._discover("providers", BaseProvider, self.providers)
        self._discover("plugins", BasePlugin, self.widgets)

    def _discover(self, directory: str, base_class, registry: dict):
        """Universal directory scanner using inspect"""
        full_directory_path = os.path.join(BASE_DIR, directory)
        
        if not os.path.exists(full_directory_path): 
            print(f"[-] Directory not found: {full_directory_path}")
            return

        if BASE_DIR not in sys.path:
            sys.path.insert(0, BASE_DIR)

        is_provider = issubclass(base_class, BaseProvider)
        layer_name = "providers" if is_provider else "plugins"
        
        if layer_name not in self.config:
            self.config[layer_name] = {}
            
        config_group = self.config[layer_name]
        config_changed = False

        for entry in os.scandir(full_directory_path):
            if entry.is_dir():
                name = entry.name
                
                if name not in config_group:
                    config_group[name] = {
                        "enabled": True,
                        **({} if is_provider else {"current_theme": "index.html"})
                    }
                    config_changed = True
                
                module_config = config_group[name]
                is_enabled = module_config.get("enabled", True)

                if not is_provider and not is_enabled:
                    print(f"[-] [{layer_name.upper()}] Skipped (disabled in config): {name}")
                    try:
                        module = importlib.import_module(f"{layer_name}.{name}.main")
                        providers_found = set()
                        for _, obj in inspect.getmembers(module):
                            if inspect.isclass(obj) and issubclass(obj, base_class) and obj is not base_class:
                                topics = getattr(obj, 'subscribed_topics', []) or getattr(obj, 'trigger_topics', [])
                                for t in (topics or []):
                                    if ":" in t:
                                        providers_found.add(t.split(':')[0].lower())
                        self.plugin_providers_map[name] = list(providers_found)
                    except Exception as e:
                        logger.debug(f"Static pre-scan error for disabled {name}: {e}")
                    continue

                if name in registry:
                    continue

                try:
                    module = importlib.import_module(f"{layer_name}.{name}.main")
                    for _, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, base_class) and obj is not base_class:
                            
                            if is_provider:
                                instance = obj(provider_id=name, bus=bus)
                                registry[name] = instance
                                print(f"[+] [{layer_name.upper()}] Init class {obj.__name__}")
                            else:
                                current_theme = module_config.get("current_theme", "index.html")
                                instance = obj(
                                    name=name, 
                                    prefix=f"/widget/{name}",
                                    bus=bus,
                                    subscribed_topics=[],
                                    current_theme=current_theme
                                )
                                self.app.include_router(instance.router)
                                registry[name] = instance
                                print(f"[+] [{layer_name.upper()}] Init class {obj.__name__}")
                                
                                providers_found = set()
                                topics = getattr(instance, 'subscribed_topics', []) or getattr(instance, 'trigger_topics', [])
                                for t in (topics or []):
                                    if ":" in t:
                                        providers_found.add(t.split(':')[0].lower())
                                
                                self.plugin_providers_map[name] = list(providers_found)
                                
                except Exception as e:
                    print(f"[-] Error loading layer {layer_name} ({name}): {e}")

        if config_changed:
            self.save_current_config_to_file()

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