import asyncio
import os
import re
from urllib.parse import urlparse

import requests

from app.baseprovider import BaseProvider

EMOTE_ID_RE = re.compile(r"^[A-Za-z0-9_:-]+$")
INVISIBLE_CHARS_RE = re.compile(r"[\u200b-\u200d\ufeff\u00ad\u034f]")

REQUEST_TIMEOUT = (3, 5)
MAX_MESSAGE_LENGTH = 500
MAX_EMOTES_PER_MESSAGE = 100
MAX_TOTAL_EMOTES = 15000
MAX_EMOTE_NAME_LENGTH = 100

TWITCH_EMOTE_URL_TEMPLATE = (
    "https://static-cdn.jtvnw.net/emoticons/v2/{emote_id}/default/light/2.0"
)

ALLOWED_EMOTE_HOSTS = {
    "static-cdn.jtvnw.net",
    "cdn.7tv.app",
    "cdn.betterttv.net",
    "cdn.frankerfacez.com",
}


class INVALID_EMOJI_DATA(Exception):
    """Raised when incoming emote payload is malformed."""


def _normalize_and_validate_emote_url(url: object) -> str | None:
    if not isinstance(url, str):
        return None
    normalized = url.strip()
    if not normalized:
        return None
    if normalized.startswith("//"):
        normalized = "https:" + normalized
    try:
        parsed = urlparse(normalized)
    except Exception:
        return None
    if (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_EMOTE_HOSTS
        and parsed.port in (None, 443)
        and parsed.username is None
        and parsed.password is None
    ):
        return normalized
    return None


def validate_emote(emote: object) -> tuple[str, str] | None:
    if not isinstance(emote, dict):
        return None

    name = emote.get("name")
    emote_id = emote.get("id")

    if not isinstance(name, str) or not name or len(name) > MAX_EMOTE_NAME_LENGTH:
        return None
    if not isinstance(emote_id, str) or not EMOTE_ID_RE.fullmatch(emote_id):
        return None

    return name, emote_id


def _pick_ffz_url(urls: object) -> str | None:
    if not isinstance(urls, dict):
        return None
    raw_url = urls.get("4") or urls.get("2") or urls.get("1")
    return _normalize_and_validate_emote_url(raw_url)


def _append_text_segment(segments: list[dict], text_out: list[str], value: str) -> None:
    if not value:
        return
    text_out.append(value)
    if segments and segments[-1].get("type") == "text":
        segments[-1]["value"] += value
    else:
        segments.append({"type": "text", "value": value})


def _append_emote_segment(
    segments: list[dict],
    *,
    provider: str,
    emote_id: str | None,
    name: str,
    url: str,
) -> None:
    segments.append(
        {
            "type": "emote",
            "provider": provider,
            "id": emote_id,
            "name": name,
            "url": url,
        }
    )


def _append_plain_chunk_as_segments(
    raw_chunk: str,
    custom_emotes: dict[str, dict],
    segments: list[dict],
    text_out: list[str],
) -> None:
    if not raw_chunk:
        return

    cleaned = INVISIBLE_CHARS_RE.sub("", raw_chunk)
    if not cleaned:
        return

    if not custom_emotes:
        _append_text_segment(segments, text_out, cleaned)
        return

    tokens = cleaned.split(" ")
    for idx, token in enumerate(tokens):
        if idx > 0:
            _append_text_segment(segments, text_out, " ")

        emote_info = custom_emotes.get(token)
        if emote_info:
            text_out.append(token)
            _append_emote_segment(
                segments,
                provider=emote_info["provider"],
                emote_id=emote_info["id"],
                name=emote_info["name"],
                url=emote_info["url"],
            )
        else:
            _append_text_segment(segments, text_out, token)


class EmojiProvider(BaseProvider):
    def __init__(self, provider_id: str, bus, **kwargs):
        super().__init__(provider_id, bus, **kwargs)
        self.emote_map: dict[str, dict] = {}
        self._twitch_id_cache: dict[str, str] = {}
        self.twitch_username: str = ""

    async def start(self) -> None:
        self.running = True
        await self.subscribe_to("twitch:message", self.message)

        self.twitch_username = os.environ.get("twitch_account", "kek").strip()

        twitch_id: str | None = None
        if self.twitch_username and self.twitch_username != "kek":
            twitch_id = await asyncio.to_thread(
                self.get_twitch_id, self.twitch_username
            )

        bttv_map, seventv_map, ffz_map = await asyncio.gather(
            asyncio.to_thread(self.load_betterttv_emotes, twitch_id),
            asyncio.to_thread(self.load_7tv_emotes, twitch_id),
            asyncio.to_thread(self.load_ffz_emotes, self.twitch_username),
        )

        merged: dict[str, dict] = {}
        for source_map in (ffz_map, bttv_map, seventv_map):
            for code, info in source_map.items():
                if len(merged) >= MAX_TOTAL_EMOTES and code not in merged:
                    break
                merged[code] = info

        self.emote_map = merged
        print(f"Loaded {len(self.emote_map)} total emotes")

    async def stop(self) -> None:
        self.running = False

    def _put_emote(
        self,
        target: dict[str, dict],
        *,
        code: str,
        raw_url: str,
        provider: str,
        emote_id: str | None = None,
    ) -> None:
        if not code or len(code) > MAX_EMOTE_NAME_LENGTH:
            return
        if len(target) >= MAX_TOTAL_EMOTES and code not in target:
            return
        safe_url = _normalize_and_validate_emote_url(raw_url)
        if not safe_url:
            return
        target[code] = {
            "provider": provider,
            "id": emote_id,
            "name": code,
            "url": safe_url,
        }

    def get_twitch_id(self, username: str) -> str | None:
        if not username:
            return None
        cached = self._twitch_id_cache.get(username)
        if cached:
            return cached

        url = f"https://decapi.me/twitch/id/{username}"
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                print("Twitch ID lookup failed:", username, response.status_code)
                return None
            twitch_id = response.text.strip()
            if twitch_id:
                self._twitch_id_cache[username] = twitch_id
                return twitch_id
            return None
        except Exception as e:
            print(f"Error fetching Twitch ID for {username}: {e}")
            return None

    def load_betterttv_emotes(self, twitch_id: str | None) -> dict[str, dict]:
        result: dict[str, dict] = {}
        print("Loading BetterTTV GLOBAL emotes...")
        try:
            global_bttv_url = "https://api.betterttv.net/3/cached/emotes/global"
            res = requests.get(global_bttv_url, timeout=REQUEST_TIMEOUT)
            if res.status_code == 200:
                for emote in res.json():
                    if not isinstance(emote, dict):
                        continue
                    code = emote.get("code")
                    emote_id = emote.get("id")
                    if (
                        isinstance(code, str)
                        and isinstance(emote_id, str)
                        and EMOTE_ID_RE.fullmatch(emote_id)
                    ):
                        self._put_emote(
                            result,
                            code=code,
                            raw_url=f"https://cdn.betterttv.net/emote/{emote_id}/3x.webp",
                            provider="bttv",
                            emote_id=emote_id,
                        )
        except Exception as e:
            print(f"Error loading BetterTTV global emotes: {e}")

        if not twitch_id:
            return result

        print(f"Loading BetterTTV channel emotes for twitch_id={twitch_id}...")
        try:
            channel_bttv_url = (
                f"https://api.betterttv.net/3/cached/users/twitch/{twitch_id}"
            )
            res = requests.get(channel_bttv_url, timeout=REQUEST_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                for group in ("channelEmotes", "sharedEmotes"):
                    for emote in data.get(group, []):
                        if not isinstance(emote, dict):
                            continue
                        code = emote.get("code")
                        emote_id = emote.get("id")
                        if (
                            isinstance(code, str)
                            and isinstance(emote_id, str)
                            and EMOTE_ID_RE.fullmatch(emote_id)
                        ):
                            self._put_emote(
                                result,
                                code=code,
                                raw_url=f"https://cdn.betterttv.net/emote/{emote_id}/3x.webp",
                                provider="bttv",
                                emote_id=emote_id,
                            )
        except Exception as e:
            print(f"Error loading BetterTTV channel emotes: {e}")

        return result

    def load_7tv_emotes(self, twitch_id: str | None) -> dict[str, dict]:
        result: dict[str, dict] = {}
        print("Loading 7TV GLOBAL emotes...")
        try:
            global_url = "https://7tv.io/v3/emote-sets/global"
            global_response = requests.get(global_url, timeout=REQUEST_TIMEOUT)
            if global_response.status_code == 200:
                global_data = global_response.json()
                emotes = global_data.get("emotes", [])
                for emote in emotes:
                    parsed = validate_emote(emote)
                    if not parsed:
                        continue
                    name, emote_id = parsed
                    self._put_emote(
                        result,
                        code=name,
                        raw_url=f"https://cdn.7tv.app/emote/{emote_id}/4x.webp",
                        provider="7tv",
                        emote_id=emote_id,
                    )
                print(f"Processed {len(emotes)} global 7TV emotes")
            else:
                print("Failed to load global 7TV emotes:", global_response.status_code)
        except Exception as e:
            print(f"Error loading global 7TV emotes: {e}")

        if not twitch_id:
            return result

        print(f"Loading 7TV emotes for twitch_id={twitch_id}")
        try:
            user_url = f"https://7tv.io/v3/users/twitch/{twitch_id}"
            response = requests.get(user_url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                print("Cannot find 7TV user:", response.status_code)
                return result

            user = response.json()
            emote_set = user.get("emote_set")
            if not isinstance(emote_set, dict) or "id" not in emote_set:
                print("User has no emote set")
                return result

            set_id = emote_set["id"]
            emotes_url = f"https://7tv.io/v3/emote-sets/{set_id}"
            response = requests.get(emotes_url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                print("Cannot load 7TV emote set:", response.status_code)
                return result

            data = response.json()
            for emote in data.get("emotes", []):
                parsed = validate_emote(emote)
                if not parsed:
                    continue
                name, emote_id = parsed
                self._put_emote(
                    result,
                    code=name,
                    raw_url=f"https://cdn.7tv.app/emote/{emote_id}/4x.webp",
                    provider="7tv",
                    emote_id=emote_id,
                )
        except Exception as e:
            print(f"Error loading channel 7TV emotes: {e}")

        return result

    def load_ffz_emotes(self, username: str) -> dict[str, dict]:
        result: dict[str, dict] = {}
        print("Loading FrankerFaceZ GLOBAL emotes...")
        try:
            global_ffz_url = "https://api.frankerfacez.com/v1/set/global"
            res = requests.get(global_ffz_url, timeout=REQUEST_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                default_sets = data.get("default_sets", [])
                sets = data.get("sets", {})

                for set_id in default_sets:
                    emote_set = sets.get(str(set_id), {})
                    for emote in emote_set.get("emoticons", []):
                        if not isinstance(emote, dict):
                            continue
                        name = emote.get("name")
                        url = _pick_ffz_url(emote.get("urls"))
                        if isinstance(name, str) and url:
                            self._put_emote(
                                result,
                                code=name,
                                raw_url=url,
                                provider="ffz",
                                emote_id=str(emote.get("id")) if emote.get("id") is not None else None,
                            )
        except Exception as e:
            print(f"Error loading FrankerFaceZ global emotes: {e}")

        if not username or username == "kek":
            return result

        print(f"Loading FrankerFaceZ channel emotes for {username}...")
        try:
            channel_ffz_url = f"https://api.frankerfacez.com/v1/room/{username}"
            res = requests.get(channel_ffz_url, timeout=REQUEST_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                room = data.get("room", {})
                set_id = room.get("set")
                sets = data.get("sets", {})

                if set_id is not None and str(set_id) in sets:
                    emote_set = sets[str(set_id)]
                    for emote in emote_set.get("emoticons", []):
                        if not isinstance(emote, dict):
                            continue
                        name = emote.get("name")
                        url = _pick_ffz_url(emote.get("urls"))
                        if isinstance(name, str) and url:
                            self._put_emote(
                                result,
                                code=name,
                                raw_url=url,
                                provider="ffz",
                                emote_id=str(emote.get("id")) if emote.get("id") is not None else None,
                            )
        except Exception as e:
            print(f"Error loading FrankerFaceZ channel emotes: {e}")

        return result

    async def message(self, payload) -> None:
        if not self.running:
            return
        if not isinstance(payload, dict):
            return
        raw_payload_data = payload.get("data")
        if not isinstance(raw_payload_data, dict):
            return

        data = dict(raw_payload_data)
        raw_text = str(data.get("text", ""))[:MAX_MESSAGE_LENGTH]
        emotes_raw = str(data.get("emotes_raw", ""))
        custom_emotes = self.emote_map

        spans: list[tuple[int, int, str, str, str]] = []
        if emotes_raw and raw_text:
            text_len = len(raw_text)
            try:
                for emote_data in emotes_raw.split("/"):
                    if not emote_data or ":" not in emote_data:
                        continue
                    emote_id, positions = emote_data.split(":", 1)
                    if not EMOTE_ID_RE.fullmatch(emote_id):
                        continue
                    raw_url = TWITCH_EMOTE_URL_TEMPLATE.format(emote_id=emote_id)
                    safe_url = _normalize_and_validate_emote_url(raw_url)
                    if not safe_url:
                        continue

                    for position in positions.split(","):
                        if len(spans) >= MAX_EMOTES_PER_MESSAGE:
                            break
                        if "-" not in position:
                            continue
                        start_s, end_s = position.split("-", 1)
                        start, end = int(start_s), int(end_s) + 1
                        if 0 <= start < end <= text_len:
                            spans.append(
                                (start, end, raw_text[start:end], safe_url, emote_id)
                            )
                    if len(spans) >= MAX_EMOTES_PER_MESSAGE:
                        break
            except Exception as e:
                print(f"Error parsing Twitch emotes: {e}")
                spans.clear()

        if len(spans) > 1:
            spans.sort(key=lambda item: item[0])

        segments: list[dict] = []
        text_parts: list[str] = []
        cursor = 0

        for start, end, emote_code, safe_url, emote_id in spans:
            if start < cursor:
                continue
            if start > cursor:
                _append_plain_chunk_as_segments(
                    raw_text[cursor:start], custom_emotes, segments, text_parts
                )

            cleaned_code = INVISIBLE_CHARS_RE.sub("", emote_code)
            if cleaned_code:
                text_parts.append(cleaned_code)
                _append_emote_segment(
                    segments,
                    provider="twitch",
                    emote_id=emote_id,
                    name=cleaned_code,
                    url=safe_url,
                )
            cursor = end

        if cursor < len(raw_text):
            _append_plain_chunk_as_segments(
                raw_text[cursor:], custom_emotes, segments, text_parts
            )

        clean_text = "".join(text_parts).strip()
        if segments and segments[0].get("type") == "text":
            segments[0]["value"] = segments[0]["value"].lstrip()
            if not segments[0]["value"]:
                segments.pop(0)
        if segments and segments[-1].get("type") == "text":
            segments[-1]["value"] = segments[-1]["value"].rstrip()
            if not segments[-1]["value"]:
                segments.pop()

        data["text"] = clean_text
        data["segments"] = segments
        data.pop("html_text", None)

        await self.emit("message", data)