import asyncio
import os
import json
import websockets
from app.baseprovider import BaseProvider

class DiscordProvider(BaseProvider):
    def __init__(self, provider_id: str, bus, **kwargs):
        super().__init__(provider_id, bus, **kwargs)
        self.client_id = "207646673902501888" # Client ID StreamKit
        self.rpc_uri = f"ws://127.0.0.1:6463/rpc?v=1&client_id={self.client_id}"
        
        self.token_file = os.path.join(os.path.dirname(__file__), "token.json")
        self.token = self._load_saved_token()
        self.streamkit_url = "" 
        
        if self.streamkit_url:
            self._extract_token_from_url()

    def _load_saved_token(self) -> str | None:
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("access_token")
            except Exception as e:
                print(f"[-] [{self.provider_id}] Error read token.json: {e}")
        return None

    def _save_token(self, token: str):
        self.token = token
        try:
            with open(self.token_file, "w", encoding="utf-8") as f:
                json.dump({"access_token": token}, f)
            print(f"[+] [{self.provider_id}] Token successfully saved to token.json for auto-login.")
        except Exception as e:
            print(f"[-] [{self.provider_id}] Failed to save the token to a file: {e}")

    def _extract_token_from_url(self):
        from urllib.parse import urlparse, parse_qs
        try:
            parsed = urlparse(self.streamkit_url)
            query_params = parse_qs(parsed.query)
            token = query_params.get('token', [None])[0]
            if token:
                print(f"[+] [{self.provider_id}] Token extracted from Streamkit URL.")
                self._save_token(token)
        except Exception as e:
            print(f"[-] [{self.provider_id}] Error retrieving token from URL: {e}")

    async def send_and_wait(self, ws, payload: dict, expected_evt: str = None) -> dict: # type: ignore
        nonce = payload.get("nonce")
        await ws.send(json.dumps(payload))
        
        while True:
            response = await ws.recv()
            data = json.loads(response)
            
            if (nonce and data.get("nonce") == nonce) or (expected_evt and data.get("evt") == expected_evt):
                return data
                
            await self._process_potential_voice_event(data)

    async def _process_potential_voice_event(self, data: dict):
        evt = data.get("evt")
        if evt in ["SPEAKING_START", "SPEAKING_STOP"]:
            user_id = data["data"]["user_id"]
            username = data["data"].get("username") or f"User_{user_id[:4]}"
            is_speaking = (evt == "SPEAKING_START")
            
            payload = {
                "user": username,
                "user_id": user_id,
                "is_speaking": is_speaking,
                "platform": "discord"
            }
            await self.emit("voice_state", payload)

    async def start(self):
        while self.running:
            try:
                print(f"[*] [{self.provider_id}] Connect to local Discord RPC...")
                headers = {"Origin": "https://streamkit.discord.com"}
                
                async with websockets.connect(self.rpc_uri, additional_headers=headers) as ws:
                    print(f"[+] [{self.provider_id}] Connection established.")
                    
                    handshake = {"cmd": "HANDSHAKE", "args": {"v": 1}, "nonce": "funny_handshake"}
                    await self.send_and_wait(ws, handshake, expected_evt="READY")
                    print(f"[+] [{self.provider_id}] Handshake successfully completed.")

                    #rpc_code = None
                    if not self.token:
                        print(f"[*] [{self.provider_id}] Token not found. Requesting access...")
                        authorize_cmd = {
                            "cmd": "AUTHORIZE",
                            "args": {
                                "client_id": self.client_id,
                                "scopes": ["rpc", "rpc.voice.read"]
                            },
                            "nonce": "funny_auth"
                        }
                        auth_resp = await self.send_and_wait(ws, authorize_cmd)
                        
                        if "data" in auth_resp and "code" in auth_resp["data"]:
                            rpc_code = auth_resp["data"]["code"]
                            print(f"[+] [{self.provider_id}] Access confirmed! Authorization code received.")
                        else:
                            print(f"[-] [{self.provider_id}] Authorization rejected by the user.")
                            await asyncio.sleep(5)
                            continue

                    auth_payload = {
                        "cmd": "AUTHENTICATE",
                        "args": {},
                        "nonce": "funny_authenticate"
                    }

                    if self.token:
                        auth_payload["args"]["access_token"] = self.token
                        auth_confirm = await self.send_and_wait(ws, auth_payload)
                    else:
                        print(f"[*] [{self.provider_id}] Token not found. Requesting Discord access...")
                        authorize_cmd = {
                            "cmd": "AUTHORIZE",
                            "args": {
                                "client_id": self.client_id,
                                "scopes": ["rpc", "rpc.voice.read"]
                            },
                            "nonce": "funny_auth"
                        }
                        auth_resp = await self.send_and_wait(ws, authorize_cmd)
                        
                        if "data" in auth_resp and "code" in auth_resp["data"]:
                            rpc_code = auth_resp["data"]["code"]
                            print(f"[+] [{self.provider_id}] Access granted! Exchanging authorization code for an access token...")
                            
                            auth_payload["args"] = {
                                "client_id": self.client_id,
                                "code": rpc_code
                            }
                            auth_confirm = await self.send_and_wait(ws, auth_payload)
                        else:
                            print(f"[-] [{self.provider_id}] Authorization was denied by the user.")
                            await asyncio.sleep(5)
                            continue

                    if auth_confirm.get("evt") == "ERROR":
                        print(f"[-] [{self.provider_id}] Authentication error: {auth_confirm['data'].get('message')}")
                        if self.token:
                            print(f"[*] [{self.provider_id}] Clearing old token...")
                            self.token = None
                            if os.path.exists(self.token_file):
                                os.remove(self.token_file)
                        await asyncio.sleep(5)
                        continue

                    if not self.token and "data" in auth_confirm and "access_token" in auth_confirm["data"]:
                        self._save_token(auth_confirm["data"]["access_token"])

                    channel_id = None
                    if "data" in auth_confirm and "user" in auth_confirm["data"]:
                        username = auth_confirm['data']['user']['username']
                        print(f"[+] [{self.provider_id}] Successfully logged in as: {username}")
                        
                        print(f"[*] [{self.provider_id}] Checking current voice channel...")
                        get_selected_channel = {
                            "cmd": "GET_SELECTED_VOICE_CHANNEL",
                            "args": {},
                            "nonce": "get_channel"
                        }
                        chan_resp = await self.send_and_wait(ws, get_selected_channel)
                        
                        if chan_resp.get("data") and chan_resp["data"].get("id"):
                            channel_id = chan_resp["data"]["id"]
                            channel_name = chan_resp["data"].get("name", "Unknown Channel")
                            print(f"[+] [{self.provider_id}] Active voice channel detected: \"{channel_name}\" (ID: {channel_id})")
                    
                    if not channel_id:
                        print(f"[-] [{self.provider_id}] You are not connected to a Discord voice channel. Waiting...")
                        await asyncio.sleep(5)
                        continue

                    await ws.send(json.dumps({"cmd": "SUBSCRIBE", "args": {"channel_id": channel_id}, "evt": "SPEAKING_START", "nonce": "sub1"}))
                    await ws.send(json.dumps({"cmd": "SUBSCRIBE", "args": {"channel_id": channel_id}, "evt": "SPEAKING_STOP", "nonce": "sub2"}))
                    print(f"[+] [{self.provider_id}] Voice activity monitoring started successfully!")

                    while self.running:
                        response = await ws.recv()
                        data = json.loads(response)
                        await self._process_potential_voice_event(data)

            except Exception as e:
                print(f"[-] [{self.provider_id}] RPC error: {repr(e)}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)