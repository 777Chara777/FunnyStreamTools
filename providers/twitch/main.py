import asyncio
import re
import os
import websockets
from app.baseprovider import BaseProvider

class TwitchProvider(BaseProvider):
    async def start(self):
        uri = "wss://irc-ws.chat.twitch.tv:443"
        channel = os.environ.get("twitch_account", "youre_twitch_name_hier_wowow")
        
        while self.running:
            try:
                print(f"[*] [{self.provider_id}] Connecting to Twitch #{channel}...")
                async with websockets.connect(uri) as websocket:
                    await websocket.send("PASS SCHMOOPIE")
                    await websocket.send("NICK justinfan12345")
                    await websocket.send(f"JOIN #{channel}")
                    
                    print(f"[+] [{self.provider_id}] Connected!")

                    while self.running:
                        raw_data: str = await websocket.recv() # type: ignore
                        
                        if raw_data.startswith("PING"):
                            await websocket.send("PONG :tmi.twitch.tv")
                            continue

                        match = re.search(r":([^!]+)!.*?PRIVMSG #.*? :(.*)", raw_data)
                        if match:
                            payload = {
                                "user": match.group(1),
                                "text": match.group(2).strip(),
                                "platform": "twitch"
                            }
                            await self.emit("message", payload)

            except Exception as e:
                print(f"[-] [{self.provider_id}] Error: {e}. Reconect...")
                await asyncio.sleep(5)