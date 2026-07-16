import re

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from app.baseplugin import BasePlugin
from app.eventbus import EventBus



class EmojiCombo(BasePlugin):
    def __init__(self, name: str, prefix: str, bus: EventBus, subscribed_topics, **kwargs):
        super().__init__(name, prefix, bus, ["chatemoji:message"], **kwargs)

        self.current_emote_src = None
        self.combo_count = 0
        
        self.emote_regex = re.compile(r'^<img[^>]+src="([^"]+)"[^>]*>$')

    def handle_payload(self, payload: dict) -> dict:
        data = payload["data"]
        html_text = data.get("html_text", "").strip()

        match = self.emote_regex.match(html_text)
        
        if match:
            emote_src = match.group(1) 
            
            if emote_src == self.current_emote_src:
                self.combo_count += 1
            else:
                self.current_emote_src = emote_src
                self.combo_count = 1
                
            return {
                "type": "combo",
                "emote": self.current_emote_src,
                "count": self.combo_count
            }
        else:
            self.current_emote_src = None
            self.combo_count = 0
            return {
                "type": "reset"
            }

    def setup_routes(self):
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