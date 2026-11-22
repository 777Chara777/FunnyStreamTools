import asyncio

from fastapi import WebSocket

SEND_TIMEOUT = 2.0


class CoreManager:
    def __init__(self):
        self._rooms: dict[str, set[WebSocket]] = {}

    async def connect(self, plugin_name: str, websocket: WebSocket):
        await websocket.accept()
        if plugin_name not in self._rooms:
            self._rooms[plugin_name] = set()
        self._rooms[plugin_name].add(websocket)

    def disconnect(self, plugin_name: str, websocket: WebSocket):
        room = self._rooms.get(plugin_name)
        if room is None:
            return
        room.discard(websocket)
        if not room:
            self._rooms.pop(plugin_name, None)

    async def _safe_send_json(self, ws: WebSocket, message: dict):
        await asyncio.wait_for(ws.send_json(message), timeout=SEND_TIMEOUT)

    async def broadcast_to_plugin(self, plugin_name: str, message: dict):
        """Send a message to a specific plugin"""
        room = self._rooms.get(plugin_name)
        if not room:
            return

        targets = list(room)
        results = await asyncio.gather(
            *(self._safe_send_json(ws, message) for ws in targets),
            return_exceptions=True,
        )

        for ws, result in zip(targets, results):
            if isinstance(result, Exception):
                self.disconnect(plugin_name, ws)

    async def broadcast_to_all(self, message: dict):
        """Send a message to all plugins (e.g., a new chat message)"""
        for plugin_name in list(self._rooms.keys()):
            await self.broadcast_to_plugin(plugin_name, message)


stream_hub = CoreManager()