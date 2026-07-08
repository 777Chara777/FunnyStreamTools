import asyncio
from typing import Dict, Set
from fastapi import WebSocket

class CoreManager:
    def __init__(self):
        # structure: {"name_plugin": {set_of_websockets}}
        self._rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, plugin_name: str, websocket: WebSocket):
        await websocket.accept()
        if plugin_name not in self._rooms:
            self._rooms[plugin_name] = set()
        self._rooms[plugin_name].add(websocket)

    def disconnect(self, plugin_name: str, websocket: WebSocket):
        if plugin_name in self._rooms:
            self._rooms[plugin_name].remove(websocket)
            if not self._rooms[plugin_name]:
                del self._rooms[plugin_name]

    async def broadcast_to_plugin(self, plugin_name: str, message: dict):
        """Send a message to a specific plugin"""
        if plugin_name in self._rooms:
            targets = list(self._rooms[plugin_name])
            await asyncio.gather(*[ws.send_json(message) for ws in targets], return_exceptions=True)

    async def broadcast_to_all(self, message: dict):
        """Send a message to all plugins (e.g., a new chat message)"""
        for plugin_name in list(self._rooms.keys()):
            await self.broadcast_to_plugin(plugin_name, message)

stream_hub = CoreManager()