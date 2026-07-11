import os
from fastapi import Request
from fastapi.responses import JSONResponse
from app.baseplugin import BasePlugin

class DashboardPlugin(BasePlugin):
    def setup_routes(self):
        @self.router.get("/api/config")
        async def get_current_config():
            from app.main import engine
            
            available_themes = {}
            for plugin_name in engine.widgets.keys():
                plugin_dir = os.path.dirname(os.path.abspath(__file__)).replace("dashboard", plugin_name)
                if os.path.exists(plugin_dir):
                    themes = [f for f in os.listdir(plugin_dir) if f.endswith(".html")]
                    available_themes[plugin_name] = themes

            return {
                "config": engine.config,
                "available_themes": available_themes
            }

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