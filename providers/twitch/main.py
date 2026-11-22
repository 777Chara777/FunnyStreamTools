import asyncio
import html
import os
import random
import re

import websockets

from app.baseprovider import BaseProvider

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
IRC_LINE_RE = re.compile(
    r"^(?:@(?P<tags>[^\s]+)\s+)?"
    r"(?::(?P<prefix>[^\s]+)\s+)?"
    r"(?P<command>[A-Z0-9]+)"
    r"(?:\s+(?P<params>[^:]+?))?"
    r"(?:\s+:(?P<trailing>.*))?$"
)

TAG_UNESCAPE_MAP = {
    r"\:": ";",
    r"\s": " ",
    r"\\": "\\",
    r"\r": "\r",
    r"\n": "\n",
}
TAG_UNESCAPE_RE = re.compile(r"\\[:s\\rn]")


class TwitchProvider(BaseProvider):
    def get_random_color(self) -> str:
        """Gen funny hex-color"""
        return "#" + "".join(random.choices("456789ABCDEF", k=6))

    def _sanitize_color(self, color: str | None) -> str:
        if color and HEX_COLOR_RE.match(color):
            return color
        return self.get_random_color()

    def _unescape_tag_value(self, value: str) -> str:
        return TAG_UNESCAPE_RE.sub(lambda m: TAG_UNESCAPE_MAP[m.group(0)], value)

    def _parse_tags(self, tags_raw: str | None) -> dict[str, str]:
        if not tags_raw:
            return {}
        tags: dict[str, str] = {}
        for item in tags_raw.split(";"):
            if "=" in item:
                key, val = item.split("=", 1)
                tags[key] = self._unescape_tag_value(val)
        return tags

    def _parse_badges(self, badges_raw: str) -> dict[str, str]:
        if not badges_raw:
            return {}
        badges: dict[str, str] = {}
        for badge in badges_raw.split(","):
            if "/" in badge:
                name, version = badge.split("/", 1)
                badges[name] = version
        return badges

    def _parse_emotes(self, emotes_raw: str) -> list[dict[str, int | str]]:
        """Возвращает плоский список смайлов с индексами для удобного рендера."""
        if not emotes_raw:
            return []
        result = []
        for emote_group in emotes_raw.split("/"):
            if ":" not in emote_group:
                continue
            emote_id, positions = emote_group.split(":", 1)
            for pos in positions.split(","):
                if "-" not in pos:
                    continue
                start_str, end_str = pos.split("-", 1)
                if start_str.isdigit() and end_str.isdigit():
                    result.append({
                        "id": emote_id,
                        "start": int(start_str),
                        "end": int(end_str),
                    })
        result.sort(key=lambda item: int(item["start"]))
        return result

    def _build_safe_html_text(self, message_text: str, emotes_raw: str) -> str:
        _ = emotes_raw
        return html.escape(message_text, quote=True)

    def _extract_user_meta(self, tags: dict[str, str], prefix: str) -> dict:
        login = prefix.split("!", 1)[0] if prefix else ""
        display_name = tags.get("display-name") or login
        badges = self._parse_badges(tags.get("badges", ""))
        badge_info = self._parse_badges(tags.get("badge-info", ""))

        is_broadcaster = "broadcaster" in badges
        is_mod = tags.get("mod") == "1" or is_broadcaster
        is_vip = "vip" in badges or tags.get("vip") == "1"
        is_sub = tags.get("subscriber") == "1" or "subscriber" in badges or "founder" in badges

        return {
            "user": str(display_name),
            "login": str(login),
            "userId": tags.get("user-id", ""),
            "color": self._sanitize_color(tags.get("color")),
            "badges": badges,
            "badgeInfo": badge_info,
            "isMod": is_mod,
            "isBroadcaster": is_broadcaster,
            "isVip": is_vip,
            "isSubscriber": is_sub,
            "isTurbo": tags.get("turbo") == "1",
        }

    def _build_message_payload(self, tags: dict[str, str], prefix: str, message_text: str) -> dict:
        user_meta = self._extract_user_meta(tags, prefix)
        emotes_raw = tags.get("emotes", "")
        safe_text = str(message_text)

        reply = None
        if tags.get("reply-parent-msg-id"):
            reply = {
                "msgId": tags.get("reply-parent-msg-id", ""),
                "userId": tags.get("reply-parent-user-id", ""),
                "userLogin": tags.get("reply-parent-user-login", ""),
                "displayName": tags.get("reply-parent-display-name", ""),
                "text": tags.get("reply-parent-msg-body", ""),
            }

        bits_raw = tags.get("bits", "0")
        bits = int(bits_raw) if bits_raw.isdigit() else 0

        return {
            **user_meta,
            "platform": "twitch",
            "msgId": tags.get("id", ""),
            "roomId": tags.get("room-id", ""),
            "timestamp": int(tags["tmi-sent-ts"]) if tags.get("tmi-sent-ts", "").isdigit() else None,
            "text": safe_text,
            "html_text": self._build_safe_html_text(safe_text, emotes_raw),
            "emotes_raw": emotes_raw,
            "emotes": self._parse_emotes(emotes_raw),
            "bits": bits,
            "isFirstMsg": tags.get("first-msg") == "1",
            "isHighlighted": tags.get("msg-id") == "highlighted-message",
            "customRewardId": tags.get("custom-reward-id") or None,
            "reply": reply,
        }

    async def start(self):
        uri = "wss://irc-ws.chat.twitch.tv:443"
        channel = os.environ.get("twitch_account", "youre_twitch_name_hier_wowow").lower()

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
                        raw_data: str = await websocket.recv()  # type: ignore

                        for line in raw_data.split("\r\n"):
                            if not line:
                                continue

                            if line.startswith("PING"):
                                await websocket.send("PONG :tmi.twitch.tv")
                                continue

                            match = IRC_LINE_RE.match(line)
                            if not match:
                                continue

                            tags = self._parse_tags(match.group("tags"))
                            prefix = match.group("prefix") or ""
                            command = match.group("command")
                            trailing = (match.group("trailing") or "").strip()

                            if command == "PRIVMSG":
                                payload = self._build_message_payload(tags, prefix, trailing)
                                await self.emit("message", payload)

                            elif command == "USERNOTICE":
                                user_meta = self._extract_user_meta(tags, prefix)
                                notice_payload = {
                                    **user_meta,
                                    "platform": "twitch",
                                    "msgId": tags.get("id", ""),
                                    "eventType": tags.get("msg-id", ""),
                                    "systemMsg": tags.get("system-msg", ""),
                                    "text": trailing,
                                    "html_text": self._build_safe_html_text(trailing, tags.get("emotes", "")),
                                    "params": {
                                        k.removeprefix("msg-param-"): v
                                        for k, v in tags.items()
                                        if k.startswith("msg-param-")
                                    },
                                }
                                await self.emit("usernotice", notice_payload)

                            elif command == "CLEARCHAT":
                                duration = tags.get("ban-duration")
                                await self.emit("clearchat", {
                                    "platform": "twitch",
                                    "targetUser": trailing or None,
                                    "targetUserId": tags.get("target-user-id"),
                                    "duration": int(duration) if duration and duration.isdigit() else None,
                                })

                            elif command == "CLEARMSG":
                                await self.emit("clearmsg", {
                                    "platform": "twitch",
                                    "targetUser": tags.get("login", ""),
                                    "targetMsgId": tags.get("target-msg-id", ""),
                                    "deletedText": trailing,
                                })

                            elif command in ("JOIN", "PART"):
                                login = prefix.split("!", 1)[0]
                                if not login.startswith("justinfan"):
                                    await self.emit(command.lower(), {
                                        "platform": "twitch",
                                        "user": login,
                                    })

                            elif command == "ROOMSTATE":
                                await self.emit("roomstate", {
                                    "platform": "twitch",
                                    "roomId": tags.get("room-id"),
                                    "emoteOnly": tags.get("emote-only") == "1",
                                    "subsOnly": tags.get("subs-only") == "1",
                                    "r9k": tags.get("r9k") == "1",
                                    "slow": int(tags["slow"]) if tags.get("slow", "").isdigit() else 0,
                                    "followersOnly": int(tags["followers-only"]) if tags.get("followers-only", "-1").lstrip("-").isdigit() else -1,
                                })
            except Exception as e:
                print(f"[-] [{self.provider_id}] Error: {e}. Reconnect...")
                await asyncio.sleep(5)
