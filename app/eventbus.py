import asyncio
from typing import Dict, Set, Callable, Literal
from fastapi import WebSocket

class EventBus:
    def __init__(self):
        # structure: { "provider_id:event_type": { websocket } }
        # exsapmle: { "twitch:message": {ws1}, "system:clear": {ws1} }
        self.topics: Dict[str, Dict[Literal["callback", "websocket"], (Set[WebSocket] | Callable)]] = {}

    async def subscribe(self, topic: str, websocket: WebSocket, callback_function: Callable):
        if topic not in self.topics:
            self.topics[topic] = {
                "websocket": set()
            }
        self.topics[topic]["websocket"].add(websocket)
        self.topics[topic]["callback"] = callback_function

    def unsubscribe_all(self, websocket: WebSocket):
        for topic_set in self.topics.values():
            if websocket in topic_set:
                topic_set["websocket"].remove(websocket)

    async def publish(self, topic: str, payload: dict):
        if topic in self.topics:
            topic_data = self.topics[topic]
            targets = list(topic_data["websocket"]) # type: ignore
            message = topic_data["callback"]( {"topic": topic, "data": payload} ) # type: ignore
            await asyncio.gather(
                *[ws.send_json(message) for ws in targets],
                return_exceptions=True
            )

bus = EventBus()