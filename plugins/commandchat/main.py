import os
import json
import re
import requests

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from app.baseplugin import BasePlugin


class CommandChatPlugin(BasePlugin):

    def __init__(
        self,
        name: str,
        prefix: str,
        bus,
        subscribed_topics: list,
        **kwargs
    ):
        super().__init__(
            name,
            prefix,
            bus,
            subscribed_topics,
            **kwargs
        )

        self.subscribed_topics = ["twitch:message"]
        self.emote_map = {}
        self.twitch_username = os.environ.get("twitch_account", "kek")

        if self.twitch_username: 
            self.load_7tv_emotes(self.twitch_username)
            self.load_betterttv_emotes(self.twitch_username) 
            self.load_ffz_emotes(self.twitch_username)
        
        print(f"Loaded {len(self.emote_map)} total emotes")

    def get_twitch_id(self, username):
        url = f"https://decapi.me/twitch/id/{username}"
        response = requests.get(url)
        if response.status_code != 200:
            print("7TV user not found:", username, response)
            return None
        return response.text

    def load_betterttv_emotes(self, username):
        print("Loading BetterTTV GLOBAL emotes...")
        try:
            global_bttv_url = "https://api.betterttv.net/3/cached/emotes/global"
            res = requests.get(global_bttv_url)
            if res.status_code == 200:
                for emote in res.json():
                    self.emote_map[emote["code"]] = f"https://cdn.betterttv.net/emote/{emote['id']}/3x.webp"
        except Exception as e:
            print(f"Error loading BetterTTV global emotes: {e}")

        if not username or username == "kek":
            return

        print(f"Loading BetterTTV channel emotes for {username}...")
        try:
            twitch_id = self.get_twitch_id(username)
            if twitch_id:
                channel_bttv_url = f"https://api.betterttv.net/3/cached/users/twitch/{twitch_id}"
                res = requests.get(channel_bttv_url)
                if res.status_code == 200:
                    data = res.json()
                    for emote in data.get("channelEmotes", []):
                        self.emote_map[emote["code"]] = f"https://cdn.betterttv.net/emote/{emote['id']}/3x.webp"
                    for emote in data.get("sharedEmotes", []):
                        self.emote_map[emote["code"]] = f"https://cdn.betterttv.net/emote/{emote['id']}/3x.webp"
        except Exception as e:
            print(f"Error loading BetterTTV channel emotes: {e}")

    def load_7tv_emotes(self, username):
        print("Loading 7TV GLOBAL emotes...")
        try:
            global_url = "https://7tv.io/v3/emote-sets/global"
            global_response = requests.get(global_url)
            if global_response.status_code == 200:
                global_data = global_response.json()
                for emote in global_data.get("emotes", []):
                    name = emote["name"]
                    emote_id = emote["id"]
                    self.emote_map[name] = f"https://cdn.7tv.app/emote/{emote_id}/4x.webp"
                print(f"Loaded {len(global_data.get('emotes', []))} global 7TV emotes")
            else:
                print("Failed to load global 7TV emotes")
        except Exception as e:
            print(f"Error loading global emotes: {e}")

        if not username or username == "kek":
            return

        print(f"Loading 7TV emotes for {username}")
        twitch_id = self.get_twitch_id(username)
        if not twitch_id:
            return

        user_url = f"https://7tv.io/v3/users/twitch/{twitch_id}"
        response = requests.get(user_url)
        if response.status_code != 200:
            print("Cannot find 7TV user")
            return

        user = response.json()
        if "emote_set" not in user:
            print("User has no emote set")
            return

        set_id = user["emote_set"]["id"]
        emotes_url = f"https://7tv.io/v3/emote-sets/{set_id}"
        response = requests.get(emotes_url)
        if response.status_code != 200:
            print("Cannot load emote set")
            return

        data = response.json()
        for emote in data.get("emotes", []):
            name = emote["name"]
            emote_id = emote["id"]
            self.emote_map[name] = f"https://cdn.7tv.app/emote/{emote_id}/4x.webp"

    def load_ffz_emotes(self, username: str):
        print("Loading FrankerFaceZ GLOBAL emotes...")
        try:
            global_ffz_url = "https://api.frankerfacez.com/v1/set/global"
            res = requests.get(global_ffz_url)
            if res.status_code == 200:
                data = res.json()
                default_sets = data.get("default_sets", [])
                sets = data.get("sets", {})
                
                for set_id in default_sets:
                    emote_set = sets.get(str(set_id), {})
                    for emote in emote_set.get("emoticons", []):
                        name = emote["name"]
                        urls = emote.get("urls", {})
                        emote_url = urls.get("4") or urls.get("2") or urls.get("1")
                        if emote_url:
                            if emote_url.startswith("//"):
                                emote_url = "https:" + emote_url
                            self.emote_map[name] = emote_url
        except Exception as e:
            print(f"Error loading FrankerFaceZ global emotes: {e}")

        if not username or username == "kek":
            return

        print(f"Loading FrankerFaceZ channel emotes for {username}...")
        try:
            channel_ffz_url = f"https://api.frankerfacez.com/v1/room/{username}"
            res = requests.get(channel_ffz_url)
            if res.status_code == 200:
                data = res.json()
                room = data.get("room", {})
                set_id = room.get("set")
                sets = data.get("sets", {})
                
                if set_id and str(set_id) in sets:
                    emote_set = sets[str(set_id)]
                    for emote in emote_set.get("emoticons", []):
                        name = emote["name"]
                        urls = emote.get("urls", {})
                        emote_url = urls.get("4") or urls.get("2") or urls.get("1")
                        if emote_url:
                            if emote_url.startswith("//"):
                                emote_url = "https:" + emote_url
                            self.emote_map[name] = emote_url
        except Exception as e:
            print(f"Error loading FrankerFaceZ channel emotes: {e}")
        

    def handle_payload(self, payload: dict) -> dict:
        text = payload["data"]["text"]

        text = re.sub(r'[\u200b-\u200d\ufeff\u00ad\u034f]', '', text)
        text = text.strip()
        payload["data"]["text"] = text

        emotes_raw = payload["data"].get("emotes_raw", "")

        html_text = text
        if emotes_raw:
            replacements = []
            try:
                for emote_data in emotes_raw.split("/"):
                    if not emote_data:
                        continue
                    emote_id, positions = emote_data.split(":")
                    for position in positions.split(","):
                        start, end = map(int, position.split("-"))
                        img_tag = f'<img src="https://static-cdn.jtvnw.net/emoticons/v2/{emote_id}/default/light/2.0" class="emote">'
                        replacements.append({
                            "start": start,
                            "end": end + 1,
                            "html": img_tag
                        })
                
                replacements.sort(key=lambda x: x["start"], reverse=True)
                
                for r in replacements:
                    html_text = html_text[:r["start"]] + r["html"] + html_text[r["end"]:]
            except Exception as e:
                print(f"Error parsing Twitch emotes: {e}")
                html_text = text

        words = html_text.split(" ")
        processed = []
        for word in words:
            if word in self.emote_map:
                processed.append(f'<img src="{self.emote_map[word]}" class="emote">')
            else:
                processed.append(word)

        payload["data"]["html_text"] = " ".join(processed)
        return payload
    
    def setup_routes(self):
        # plugin_dir = os.path.dirname(__file__)
        # html_path = os.path.join(plugin_dir, "index.html")

        # @self.router.get("", response_class=HTMLResponse)
        # async def get_widget():
        #     with open(html_path, "r", encoding="utf-8") as f:
        #         return f.read()

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