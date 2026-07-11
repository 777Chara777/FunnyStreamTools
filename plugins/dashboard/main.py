import os
from fastapi import Request
from fastapi.responses import JSONResponse
from app.baseplugin import BasePlugin
from app.eventbus import EventBus

class DashboardPlugin(BasePlugin):
    def __init__(self, name: str, prefix: str, bus: EventBus, subscribed_topics: list, **kwargs):
        super().__init__(name, prefix, bus, subscribed_topics, **kwargs)

    def setup_routes(self):
        @self.router.post("/api/config")
        async def save_config(payload: dict):
            from app.main import engine
            engine.update_and_save_config(payload)
            return {"status": "success", "message": "Configuration updated!"}
        
        @self.router.post("/api/reload")
        async def reload_server_modules():
            from app.main import engine
            await engine.reload_modules()
            return {"status": "success", "message": "Disk modules successfully rescanned!"}
        
        @self.router.get("/api/config")
        async def get_current_config():
            from app.main import engine
            
            available_themes = {}
            dashboard_dir = os.path.dirname(os.path.abspath(__file__))
            plugins_base_dir = os.path.dirname(dashboard_dir)
            
            if os.path.exists(plugins_base_dir):
                for entry in os.scandir(plugins_base_dir):
                    if entry.is_dir():
                        plugin_dir = entry.path
                        themes = [f for f in os.listdir(plugin_dir) if f.endswith(".html")]
                        available_themes[entry.name] = themes if themes else ["index.html"]

            plugin_providers = engine.plugin_providers_map

            current_config = engine.config
            active_plugins = [p for p, c in current_config.get("plugins", {}).items() if c.get("enabled", True)]
            active_providers = [p for p, c in current_config.get("providers", {}).items() if c.get("enabled", True)]

            missing_dependencies = {}
            for plugin in active_plugins:
                required = plugin_providers.get(plugin, [])
                missing = [p for p in required if p not in active_providers]
                if missing:
                    missing_dependencies[plugin] = missing

            return {
                "config": current_config,
                "available_themes": available_themes,
                "plugin_providers": plugin_providers,
                "missing_dependencies": missing_dependencies
            }