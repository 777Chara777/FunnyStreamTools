from urllib.parse import urlparse

from fastapi import WebSocket, WebSocketDisconnect

from app.baseplugin import BasePlugin
from app.eventbus import EventBus

ALLOWED_EMOTE_HOSTS = {
    "static-cdn.jtvnw.net",
    "cdn.7tv.app",
    "cdn.betterttv.net",
    "cdn.frankerfacez.com",
}


def _is_safe_emote_url(raw_url: object) -> str | None:
    if not isinstance(raw_url, str):
        return None
    candidate = raw_url.strip()
    if not candidate:
        return None
    try:
        parsed = urlparse(candidate)
    except Exception:
        return None
    if (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_EMOTE_HOSTS
        and parsed.port in (None, 443)
        and parsed.username is None
        and parsed.password is None
    ):
        return candidate
    return None


def _extract_single_emote_url(data: dict) -> str | None:
    """Возвращает безопасный URL эмота, если сообщение состоит ровно из одного эмота."""
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        return None

    meaningful_segments = [
        seg
        for seg in segments
        if isinstance(seg, dict)
        and not (
            seg.get("type") == "text"
            and isinstance(seg.get("value"), str)
            and not seg.get("value", "").strip()
        )
    ]

    if len(meaningful_segments) != 1:
        return None

    only_seg = meaningful_segments[0]
    if only_seg.get("type") != "emote":
        return None

    return _is_safe_emote_url(only_seg.get("url"))


class EmojiCombo(BasePlugin):
    def __init__(
        self,
        name: str,
        prefix: str,
        bus: EventBus,
        subscribed_topics,
        **kwargs,
    ):
        super().__init__(name, prefix, bus, ["chatemoji:message"], **kwargs)

        self.current_emote_src: str | None = None
        self.combo_count: int = 0

    def handle_payload(self, payload: dict) -> dict:
        raw_data = payload.get("data") if isinstance(payload, dict) else None
        data = raw_data if isinstance(raw_data, dict) else {}

        emote_src = _extract_single_emote_url(data)

        if emote_src:
            if emote_src == self.current_emote_src:
                self.combo_count += 1
            else:
                self.current_emote_src = emote_src
                self.combo_count = 1

            return {
                "type": "combo",
                "emote": self.current_emote_src,
                "count": self.combo_count,
            }

        self.current_emote_src = None
        self.combo_count = 0
        return {"type": "reset"}

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
                pass
            finally:
                self.bus.unsubscribe_all(websocket)