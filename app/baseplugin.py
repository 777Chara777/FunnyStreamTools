from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import typing
import inspect
import os

if typing.TYPE_CHECKING:
    from app.eventbus import EventBus

class BasePlugin:
    def __init__(self, name: str, prefix: str, bus: "EventBus", subscribed_topics: list, current_theme: str = "index.html", **kwargs):
        self.name = name
        self.router = APIRouter(prefix=prefix, tags=[name])
        self.bus = bus
        self.current_theme = current_theme

        self.subscribed_topics = subscribed_topics

        self.plugin_dir = os.path.dirname(inspect.getfile(self.__class__))
        
        self._setup_resource_routes()
        self.setup_routes()

    def setup_routes(self):
        """Every plugin must override this method."""
        raise NotImplementedError("Every plugin must implement the setup_routes method")
    
    def _setup_resource_routes(self):
        """Registers a root endpoint to serve the selected HTML resource."""
        @self.router.get("", response_class=HTMLResponse)
        async def render_theme():
            theme_path = os.path.join(self.plugin_dir, self.current_theme)
            
            if not os.path.exists(theme_path):
                theme_path = os.path.join(self.plugin_dir, "index.html")
                
            if not os.path.exists(theme_path):
                return HTMLResponse(content="<h1>Widget UI not found</h1>", status_code=404)
                
            with open(theme_path, "r", encoding="utf-8") as f:
                return f.read()



    def handle_payload(self, payload: dict) -> dict: return payload
