"""Feishu websocket lifecycle management."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable

import lark_oapi as lark
from homeassistant.core import HomeAssistant

from .exceptions import FeishuConnectionError
from .models import IncomingMessage

_LOGGER = logging.getLogger(__name__)


class FeishuWsClient:
    """Manage Feishu websocket client and message callbacks."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        app_id: str,
        app_secret: str,
        message_handler: Callable[[IncomingMessage], Awaitable[None]],
    ) -> None:
        self._hass = hass
        self._app_id = app_id
        self._app_secret = app_secret
        self._message_handler = message_handler
        self._client: object | None = None
        self._runner_task: asyncio.Task | None = None
        self._seen_message_ids: OrderedDict[str, None] = OrderedDict()
        self._seen_limit = 512
        self._status = "disconnected"
        self._status_listeners: set[Callable[[str], None]] = set()

    @property
    def status(self) -> str:
        """Current websocket status."""
        return self._status

    def register_status_listener(self, listener: Callable[[str], None]) -> Callable[[], None]:
        """Register status callback and return unsubscribe function."""
        self._status_listeners.add(listener)
        listener(self._status)

        def _unsub() -> None:
            self._status_listeners.discard(listener)

        return _unsub

    async def async_start(self) -> None:
        """Start websocket background runner."""
        if self._runner_task is not None:
            return

        self._runner_task = self._hass.async_create_background_task(
            self._async_run_forever(),
            "feishu_bot_ws_runner",
        )

    async def async_stop(self) -> None:
        """Stop websocket background runner."""
        if self._runner_task is not None:
            self._runner_task.cancel()
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass
            self._runner_task = None

        await self._hass.async_add_executor_job(self._stop_sync)
        self._set_status("disconnected")

    async def _async_run_forever(self) -> None:
        """Maintain websocket connection with reconnect."""
        while True:
            self._set_status("connecting")
            _LOGGER.info("Connecting to Feishu websocket")
            try:
                await self._hass.async_add_executor_job(self._start_sync)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                self._set_status("error")
                _LOGGER.warning("Feishu websocket error: %s", err)

            self._set_status("disconnected")
            await asyncio.sleep(5)

    def _start_sync(self) -> None:
        builder = lark.EventDispatcherHandler.builder("", "")
        event_handler = builder.register_p2_im_message_receive_v1(self._on_message_sync).build()
        self._client = lark.ws.Client(
            self._app_id,
            self._app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )
        self._set_status("connected")
        self._client.start()

    def _stop_sync(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            stop = getattr(client, "stop", None)
            if callable(stop):
                stop()

    def _on_message_sync(self, data: object) -> None:
        event = getattr(data, "event", None)
        if event is None:
            return

        message = getattr(event, "message", None)
        sender = getattr(event, "sender", None)
        if message is None:
            return

        message_id = getattr(message, "message_id", "") or ""
        if not message_id or message_id in self._seen_message_ids:
            return

        self._seen_message_ids[message_id] = None
        self._seen_message_ids.move_to_end(message_id)
        if len(self._seen_message_ids) > self._seen_limit:
            self._seen_message_ids.popitem(last=False)

        content_raw = getattr(message, "content", "") or ""
        text = _extract_text(content_raw)
        chat_id = getattr(message, "chat_id", None)
        sender_id = None
        if sender is not None:
            sender_id_obj = getattr(sender, "sender_id", None)
            if sender_id_obj is not None:
                sender_id = (
                    getattr(sender_id_obj, "open_id", None)
                    or getattr(sender_id_obj, "user_id", None)
                    or getattr(sender_id_obj, "union_id", None)
                )

        incoming = IncomingMessage(
            message_id=message_id,
            chat_id=chat_id,
            user_id=sender_id,
            text=text,
        )

        future = asyncio.run_coroutine_threadsafe(self._message_handler(incoming), self._hass.loop)
        future.add_done_callback(_log_future_exception)

    def _set_status(self, status: str) -> None:
        if self._status == status:
            return

        self._status = status
        for listener in tuple(self._status_listeners):
            try:
                listener(status)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Failed to notify status listener")


def _extract_text(content: str) -> str:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return content.strip()

    if isinstance(payload, dict):
        return str(payload.get("text", "")).strip()
    return ""


def _log_future_exception(future: asyncio.Future) -> None:
    try:
        future.result()
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Failed to process Feishu message")
