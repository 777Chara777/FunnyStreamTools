import asyncio
import inspect
from collections.abc import Callable

from fastapi import WebSocket


class EventBus:
    def __init__(self):
        self.topics: dict[str, set[tuple[WebSocket | None, Callable]]] = {}

    async def subscribe(
        self,
        topic: str,
        websocket: WebSocket | None,
        callback_function: Callable,
    ):
        if topic not in self.topics:
            self.topics[topic] = set()
        self.topics[topic].add((websocket, callback_function))

    def unsubscribe_all(self, websocket: WebSocket):
        for topic in list(self.topics.keys()):
            self.topics[topic] = {
                pair for pair in self.topics[topic] if pair[0] != websocket
            }
            if not self.topics[topic]:
                del self.topics[topic]

    def clear(self):
        """Полная очистка всех подписок (например, при перезагрузке модулей)."""
        self.topics.clear()

    async def publish(self, topic: str, payload: dict):
        if topic not in self.topics:
            return

        subscribers = list(self.topics[topic])
        send_pairs: list[tuple[WebSocket, dict]] = []

        for websocket, callback_function in subscribers:
            try:
                if inspect.iscoroutinefunction(callback_function):
                    message = await callback_function({"topic": topic, "data": payload})
                else:
                    message = callback_function({"topic": topic, "data": payload})

                if websocket is not None and message is not None:
                    send_pairs.append((websocket, message))
            except Exception as e:
                print(f"[-] Error processing callback for {topic}: {e}")

        if not send_pairs:
            return

        results = await asyncio.gather(
            *(ws.send_json(msg) for ws, msg in send_pairs),
            return_exceptions=True,
        )

        for (ws, _), result in zip(send_pairs, results):
            if isinstance(result, Exception):
                print(f"[-] Removing dead WebSocket on topic {topic}: {result}")
                self.unsubscribe_all(ws)


bus = EventBus()