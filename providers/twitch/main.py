import re
import os
import random
import asyncio
import websockets
from app.baseprovider import BaseProvider

class TwitchProvider(BaseProvider):
    def get_random_color(self) -> str:
        """Gen funny hex-color"""
        return "#" + "".join(random.choices("456789ABCDEF", k=6))
    
    async def start(self):
        uri = "wss://irc-ws.chat.twitch.tv:443"
        channel = os.environ.get("twitch_account", "youre_twitch_name_hier_wowow")
        
        while self.running:
            try:
                print(f"[*] [{self.provider_id}] Connecting to Twitch #{channel}...")
                async with websockets.connect(uri) as websocket:
                    await websocket.send("CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership")
                    await websocket.send("PASS SCHMOOPIE")
                    await websocket.send("NICK justinfan12345")
                    await websocket.send(f"JOIN #{channel}")
                    
                    print(f"[+] [{self.provider_id}] Connected!")

                    while self.running:
                        raw_data: str = await websocket.recv() # type: ignore

                        lines = raw_data.split("\r\n")

                        for line in lines:
                            if not line:
                                continue

                            if line.startswith("PING"):
                                await websocket.send("PONG :tmi.twitch.tv")
                                continue

                            if "PRIVMSG" in line:
                                match = re.search(r"^(?:@([^\s]+)\s+)?([^ ]+)\s+PRIVMSG\s+#[^\s]+\s+:(.*)$", line)
                                
                                if match:
                                    tags_raw = match.group(1) or ""
                                    user_info = match.group(2)
                                    message_text = match.group(3).strip() 

                                    username_raw = user_info.lstrip(":").split("!", 1)[0]

                                    display_name_match = re.search(r"display-name=([^;]+)", tags_raw)
                                    username = display_name_match.group(1) if display_name_match else username_raw

                                    color_match = re.search(r"color=(#[0-9A-Fa-f]{6})", tags_raw)
                                    user_color = color_match.group(1) if color_match else self.get_random_color()

                                    is_mod = "mod=1" in tags_raw or "badges=broadcaster" in tags_raw

                                    emotes_match = re.search(r"emotes=([^;]+)", tags_raw)
                                    emotes_raw = emotes_match.group(1) if emotes_match else ""

                                    payload = {
                                        "user": username,
                                        "text": message_text,
                                        "emotes_raw": emotes_raw, 
                                        "platform": "twitch",
                                        "color": user_color,
                                        "isMod": is_mod
                                    }
                                    
                                    await self.emit("message", payload)

            except Exception as e:
                print(f"[-] [{self.provider_id}] Error: {e}. Reconect...")
                await asyncio.sleep(5)