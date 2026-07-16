import asyncio
import inspect
from typing import Dict, Set, Callable, Tuple, Optional
from fastapi import WebSocket

class EventBus:
    def __init__(self):
        # structure: { "provider_id:event_type": { websocket } }
        # exsapmle: { "twitch:message": {ws1}, "system:clear": {ws1} }
        self.topics: Dict[str, Set[Tuple[Optional[WebSocket], Callable]]] = {}

    async def subscribe(self, topic: str, websocket: Optional[WebSocket], callback_function: Callable):
        if topic not in self.topics:
            self.topics[topic] = set()
        
        self.topics[topic].add((websocket, callback_function))

    def unsubscribe_all(self, websocket: WebSocket):
        for topic in self.topics:
            self.topics[topic] = {
                pair for pair in self.topics[topic] if pair[0] != websocket
            }

    async def publish(self, topic: str, payload: dict):
        if topic in self.topics:
            tasks = []
            
            for websocket, callback_function in self.topics[topic]:
                try:
                    if inspect.iscoroutinefunction(callback_function):
                        message = await callback_function({"topic": topic, "data": payload})
                    else:
                        message = callback_function({"topic": topic, "data": payload})
                    if not websocket: continue
                    tasks.append(websocket.send_json(message))
                except Exception as e:
                    print(f"[-] Error processing callback for {topic}: {e}")

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

bus = EventBus()