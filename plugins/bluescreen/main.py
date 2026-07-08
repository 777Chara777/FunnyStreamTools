import os

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from app.baseplugin import BasePlugin


class BlueScreenMeme(BasePlugin):

    def __init__(
            self,
            name: str,
            prefix: str,
            bus,
            subscribed_topics: list,
            **kwargs
        ):
        super().__init__( name, prefix, bus, subscribed_topics, **kwargs)
        self.subscribed_topics = ["twitch:message"]
    
    def handle_payload( self, payload: dict ) -> dict:

        return {"bluescreen": payload["data"]["text"].strip().lower() == "bluescreen"}

    def setup_routes(self):
        plugin_dir = os.path.dirname(__file__)
        html_path = os.path.join(plugin_dir, "index.html")

        @self.router.get("", response_class=HTMLResponse)
        async def get_widget():
            with open(html_path, "r", encoding="utf-8") as f:
                return f.read()

        @self.router.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            
            for topic in self.subscribed_topics:
                await self.bus.subscribe(topic, websocket, self.handle_payload)
                
            try:
                while True:
                    await websocket.receive_text()  
            except WebSocketDisconnect:
                self.bus.unsubscribe_all(websocket)