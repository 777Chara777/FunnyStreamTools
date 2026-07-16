from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from eventbus import EventBus

class BaseProvider:
    def __init__(self, provider_id: str, bus, **kwargs):
        self.provider_id = provider_id
        self.bus: "EventBus" = bus
        self.running = True

    async def start(self):
        """Each provider is required to override this method.
        It will run an infinite asynchronous loop for reading data."""
        raise NotImplementedError("Each provider must implement the start method")

    async def emit(self, event_type: str, data: dict):
        """A convenient method for sending data to the bus. 
        Constructs a topic in the format 'twitch:chat_message'"""
        topic = f"{self.provider_id}:{event_type}"
        await self.bus.publish(topic, data)

    async def subscribe_to(self, topic: str, callback: Callable):
        """Allows the provider to subscribe to another topic within the Python code."""
        await self.bus.subscribe(topic, None, callback)