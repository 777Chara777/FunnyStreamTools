import asyncio

class BaseProvider:
    def __init__(self, provider_id: str, bus, **kwargs):
        self.provider_id = provider_id
        self.bus = bus
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