import os
import json
import socket
import asyncio
from app.baseprovider import BaseProvider

class MemeCanvasProvider(BaseProvider):
    def __init__(self, provider_id: str, bus, **kwargs):
        super().__init__(provider_id, bus, **kwargs)
        self.canvas_state = {}
        self.canvas_bounds = {"width": 1920, "height": 1080}
        self.global_css = ""

        self.scenes_dir = os.path.join(os.path.dirname(__file__), "presets")
        if not os.path.exists(self.scenes_dir):
            os.makedirs(self.scenes_dir)

    async def start(self):
        asyncio.create_task(self.start_udp_server())
        print(f"[+] [PROVIDER] MemeCanvasProvider ('{self.provider_id}') запущен с поддержкой Сцен и Триггеров.")
        
        while self.running:
            await asyncio.sleep(1)

    async def process_action(self, data: dict):
        t = data.get('type')
        obj_id = data.get('id')
        
        if t == 'meme_update':
            self.canvas_state[obj_id] = data
        elif t == 'meme_move' and obj_id in self.canvas_state:
            self.canvas_state[obj_id].update({'x': data['x'], 'y': data['y']})
        elif t == 'delete':
            self.canvas_state.pop(obj_id, None)
        elif t == 'clear_all':
            self.canvas_state.clear()
        elif t == 'update_bounds' or t == 'obs_init':
            self.canvas_bounds = {"width": data['width'], "height": data['height']}
            data = {"type": "update_bounds", "width": data['width'], "height": data['height']}

        elif t == 'set_global_css':
            self.global_css = data.get('css', '')
            data = {"type": "set_global_css", "css": self.global_css}

        elif t == 'save_scene':
            scene_name = data.get('scene_name', 'default_scene')
            file_path = os.path.join(self.scenes_dir, f"{scene_name}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({
                    "state": self.canvas_state,
                    "bounds": self.canvas_bounds,
                    "global_css": self.global_css,
                }, f, ensure_ascii=False, indent=4)
            return

        elif t == 'load_scene':
            scene_name = data.get('scene_name', 'default_scene')
            file_path = os.path.join(self.scenes_dir, f"{scene_name}.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.canvas_state = saved.get("state", {})
                    self.canvas_bounds = saved.get("bounds", self.canvas_bounds)
                    self.global_css = saved.get("global_css", "")
                await self.emit("canvas_changed", {"action_data": {
                    "type": "init_state",
                    "objects": list(self.canvas_state.values()),
                    "bounds": self.canvas_bounds,
                    "css": self.global_css,
                }})
                return

        elif t == 'external_trigger':
            trigger_event = data.get('event_type')
            raw_payload = data.get('raw_payload')
            for obj in self.canvas_state.values():
                if obj.get('trigger_target') == trigger_event:
                    obj['hidden'] = False
                    await self.emit("canvas_changed", {"action_data": obj})

                    duration = obj.get('trigger_duration', 5)
                    if duration:
                        asyncio.create_task(self.hide_after_delay(obj['id'], duration))
            return

        await self.emit("canvas_changed", {"action_data": data})

    async def hide_after_delay(self, obj_id, delay):
        await asyncio.sleep(delay)
        if obj_id in self.canvas_state:
            self.canvas_state[obj_id]['hidden'] = True
            await self.emit("canvas_changed", {"action_data": self.canvas_state[obj_id]})

    async def start_udp_server(self):
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', 8081))
        sock.setblocking(False)

        while self.running:
            try:
                data, _ = await loop.sock_recv(sock, 4096)
                payload = json.loads(data.decode('utf-8')) # type: ignore
                t = payload.get('type')
                obj_id = payload.get('id')
                
                if t == 'meme_move' and obj_id in self.canvas_state:
                    self.canvas_state[obj_id].update({'x': payload['x'], 'y': payload['y']})
                elif t == 'client_cursor':
                    await self.emit('client_cursor', payload)
                    
                await self.emit("canvas_changed", {"action_data": payload})
            except Exception:
                await asyncio.sleep(0.01)

# main = MemeCanvasProvider