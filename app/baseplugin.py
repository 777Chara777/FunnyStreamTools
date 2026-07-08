from fastapi import APIRouter
import typing

if typing.TYPE_CHECKING:
    from app.eventbus import EventBus

class BasePlugin:
    def __init__(self, name: str, prefix: str, bus: "EventBus", subscribed_topics: list, **kwargs):
        self.name = name
        self.router = APIRouter(prefix=prefix, tags=[name])
        self.bus = bus
        self.subscribed_topics = subscribed_topics
        
        self.setup_routes()

    def setup_routes(self):
        """Every plugin must override this method."""
        raise NotImplementedError("Every plugin must implement the setup_routes method")


    def handle_payload(self, payload: dict) -> dict: return payload
