import os
import json
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

        self.subscribed_topics = [
            "twitch:message"
        ]

        self.emote_map = {}

        self.twitch_username = os.environ.get(
            "twitch_account", "kek"
        )

        if self.twitch_username:
            self.load_7tv_emotes(
                self.twitch_username
            )


    def get_twitch_id(self, username):

        url = (
            f"https://7tv.io/v3/users/twitch/{54746959}"
            # f"twitch/{username}"
            
        )

        response = requests.get(url)

        if response.status_code != 200:
            print(
                "7TV user not found:",
                username, response
            )
            return None

        data = response.json()

        return data["id"]



    def load_7tv_emotes(self, username):

        print(f"Loading 7TV emotes for {username}")

        user_url = (
            f"https://7tv.io/v3/users/twitch/{54746959}"
            # f"twitch/{username}"
        )

        response = requests.get(
            user_url
        )
        if response.status_code != 200:
            print(
                "Cannot find 7TV user"
            )
            return

        user = response.json()

        if "emote_set" not in user:
            print("User has no emote set")
            return

        set_id = (
            user["emote_set"]["id"]
        )

        emotes_url = (
            f"https://7tv.io/v3/emote-sets/"
            f"{set_id}"
        )

        response = requests.get(
            emotes_url
        )

        if response.status_code != 200:
            print("Cannot load emote set")
            return

        data = response.json()

        for emote in data["emotes"]:

            name = emote["name"]
            emote_id = emote["id"]

            self.emote_map[name] = (
                f"https://cdn.7tv.app/emote/"
                f"{emote_id}/4x.webp"
            )

        print(f"Loaded {len(self.emote_map)} 7TV emotes")

        # print(self.emote_map.keys())

    def handle_payload(
        self,
        payload: dict
    ) -> dict:
        text = payload["data"]["text"]
        words = text.split(" ")

        processed = []
        for word in words:

            if word in self.emote_map:

                processed.append(
                    f'<img src="{self.emote_map[word]}" '
                    f'class="emote">'
                )

            else:

                processed.append(word)
        payload["data"]["html_text"] = (
            " ".join(processed)
        )


        return payload
    
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