import os
import uuid
import random
import asyncio
from fastapi import WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from app.baseplugin import BasePlugin
from app.main import engine

PRESENCE_COLORS = ["#5865F2", "#57F287", "#FEE75C", "#ED4245", "#EB459E", "#3BA55D", "#FAA61A", "#45DDEB"]

class MemeCanvasPlugin(BasePlugin):
    def __init__(self, name: str, prefix: str, bus, subscribed_topics: list = None, **kwargs): # type: ignore
        self.plugin_dir = os.path.dirname(__file__)

        self.trigger_topics = [
            "donation:alert",
            "twitch:chat_command",
        ]
        own_topics = ["memecanvas:canvas_changed"] + self.trigger_topics

        super().__init__(name, prefix, bus, own_topics, **kwargs)
        self.connected_websockets = {}
        
        self.upload_dir = os.path.join(self.plugin_dir, "uploads")
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)

    def handle_payload(self, payload: dict) -> dict:
        return payload["data"]["action_data"]

    def setup_routes(self):
        sender_path = os.path.join(self.plugin_dir, "sender.html")
        index_path = os.path.join(self.plugin_dir, "index.html")

        @self.router.get("/admin", response_class=HTMLResponse)
        async def get_admin_panel():
            with open(sender_path, "r", encoding="utf-8") as f:
                return f.read()

        @self.router.get("/widget", response_class=HTMLResponse)
        async def get_obs_widget():
            with open(index_path, "r", encoding="utf-8") as f:
                return f.read()

        @self.router.get("/file/{filename}")
        async def get_uploaded_file(filename: str):
            file_path = os.path.join(self.upload_dir, filename)
            if os.path.exists(file_path):
                return FileResponse(file_path)
            return JSONResponse(status_code=404, content={"error": "File not found"})

        @self.router.get("/scenes")
        async def list_scenes():
            provider = engine.providers.get("memecanvas")
            if not provider:
                return JSONResponse(status_code=404, content={"error": "provider not found"})
            names = [
                f[:-5] for f in os.listdir(provider.scenes_dir)
                if f.endswith(".json")
            ]
            return JSONResponse(status_code=200, content={"scenes": sorted(names)})

        @self.router.post("/upload")
        async def upload_file(file: UploadFile = File(...)):
            try:
                file_extension = os.path.splitext(file.filename)[1] # type: ignore
                unique_filename = f"{uuid.uuid4()}{file_extension}"
                file_path = os.path.join(self.upload_dir, unique_filename)
                
                with open(file_path, "wb") as f:
                    f.write(await file.read())
                
                file_url = f"file/{unique_filename}"
                
                return JSONResponse(status_code=200, content={"url": file_url, "filename": file.filename})
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.router.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()

            identity = {
                "id": uuid.uuid4().hex[:8],
                "name": f"Гость-{random.randint(1000, 9999)}",
                "color": random.choice(PRESENCE_COLORS),
            }
            self.connected_websockets[websocket] = identity

            async def async_broadcast(clean_data: dict, exclude: WebSocket = None): # type: ignore
                targets = [ws for ws in self.connected_websockets if ws is not exclude]
                if targets:
                    await asyncio.gather(
                        *[ws.send_json(clean_data) for ws in targets],
                        return_exceptions=True
                    )

            async def broadcast_presence():
                await async_broadcast({
                    "type": "presence_list",
                    "users": list(self.connected_websockets.values()),
                })

            def event_bus_bridge(event_data):
                topic = event_data.get("topic", "")

                if topic in self.trigger_topics:
                    provider = engine.providers.get("memecanvas")
                    if provider:
                        asyncio.create_task(provider.process_action({
                            "type": "external_trigger",
                            "event_type": topic,
                            "raw_payload": event_data.get("data"),
                        }))
                    return None

                clean_data = self.handle_payload(event_data)
                asyncio.create_task(async_broadcast(clean_data))
                return None

            for topic in self.subscribed_topics:
                await self.bus.subscribe(topic, websocket, event_bus_bridge)
            
            try:
                provider = engine.providers.get("memecanvas")
                if provider:
                    await websocket.send_json({
                        "type": "init_state",
                        "objects": list(provider.canvas_state.values()),
                        "bounds": provider.canvas_bounds,
                        "css": provider.global_css
                    })

                await websocket.send_json({"type": "presence_you", "you": identity})
                await broadcast_presence()

                while True:
                    data = await websocket.receive_json()

                    if data.get("type") in ("presence_select", "presence_cursor"):
                        await async_broadcast({**data, "user": identity}, exclude=websocket)
                        continue

                    if provider:
                        await provider.process_action(data)
                        
            except WebSocketDisconnect:
                self.bus.unsubscribe_all(websocket)
                self.connected_websockets.pop(websocket, None)
                await broadcast_presence()


# main = MemeCanvasPlugin