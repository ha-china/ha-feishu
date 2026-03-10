"""Feishu websocket lifecycle management."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .exceptions import FeishuAuthError, FeishuConnectionError
from .models import IncomingMessage

_LOGGER = logging.getLogger(__name__)

_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
_WS_URL = "wss://open.feishu.cn/open-apis/im/v1/messages?token={token}"


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
        self._session = async_get_clientsession(hass)
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

        self._set_status("connecting")
        self._runner_task = self._hass.async_create_background_task(
            self._async_run_forever(),
            "feishu_bot_ws_runner",
        )

    async def async_stop(self) -> None:
        """Stop websocket background runner."""
        if self._runner_task is None:
            return

        self._runner_task.cancel()
        try:
            await self._runner_task
        except asyncio.CancelledError:
            pass
        self._runner_task = None
        self._set_status("disconnected")

    async def _async_run_forever(self) -> None:
        """Maintain websocket connection with reconnect."""
        while True:
            try:
                token = await self._async_get_tenant_access_token()
                ws_url = _WS_URL.format(token=token)
                _LOGGER.info("Connecting to Feishu websocket")
                self._set_status("connecting")

                async with self._session.ws_connect(ws_url, heartbeat=30) as websocket:
                    _LOGGER.info("Feishu websocket connected")
                    self._set_status("connected")
                    async for msg in websocket:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._async_handle_ws_text(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            raise FeishuConnectionError(str(websocket.exception()))
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                            break

                _LOGGER.warning("Feishu websocket disconnected, retrying in 5s")
                self._set_status("disconnected")
            except asyncio.CancelledError:
                raise
            except (FeishuAuthError, FeishuConnectionError, aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.warning("Feishu websocket error: %s", err)
                self._set_status("error")
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unexpected Feishu websocket error: %s", err)
                self._set_status("error")

            await asyncio.sleep(5)

    async def _async_get_tenant_access_token(self) -> str:
        payload = {"app_id": self._app_id, "app_secret": self._app_secret}
        async with asyncio.timeout(15):
            response = await self._session.post(_TOKEN_URL, json=payload)

        try:
            data = await response.json(content_type=None)
        except Exception as err:  # noqa: BLE001
            body = await response.text()
            raise FeishuAuthError(f"token response parse failed status={response.status} body={body[:200]}") from err

        if response.status != 200 or data.get("code") != 0:
            raise FeishuAuthError(f"token request failed: {data.get('msg', response.reason)}")

        token = data.get("tenant_access_token")
        if not token:
            raise FeishuAuthError("token request succeeded but token missing")
        return token

    async def _async_handle_ws_text(self, raw_text: str) -> None:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            _LOGGER.debug("Ignore non-json websocket payload")
            return

        event = payload.get("event") or {}
        message = event.get("message")
        if not isinstance(message, dict):
            return

        message_id = str(message.get("message_id") or "")
        if not message_id or message_id in self._seen_message_ids:
            return

        self._seen_message_ids[message_id] = None
        self._seen_message_ids.move_to_end(message_id)
        if len(self._seen_message_ids) > self._seen_limit:
            self._seen_message_ids.popitem(last=False)

        chat_id = message.get("chat_id")
        sender = event.get("sender") or message.get("sender") or {}
        sender_id = _extract_sender_id(sender)
        text = _extract_text(message.get("content"))

        incoming = IncomingMessage(
            message_id=message_id,
            chat_id=chat_id,
            user_id=sender_id,
            text=text,
        )
        await self._message_handler(incoming)

    def _set_status(self, status: str) -> None:
        if self._status == status:
            return
        self._status = status
        for listener in tuple(self._status_listeners):
            try:
                listener(status)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Failed to notify status listener")


def _extract_text(content: object) -> str:
    if not isinstance(content, str):
        return ""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return content.strip()
    if isinstance(payload, dict):
        return str(payload.get("text", "")).strip()
    return ""


def _extract_sender_id(sender: object) -> str | None:
    if not isinstance(sender, dict):
        return None

    sender_id = sender.get("sender_id")
    if isinstance(sender_id, dict):
        for key in ("open_id", "user_id", "union_id"):
            value = sender_id.get(key)
            if isinstance(value, str) and value:
                return value

    for key in ("id", "open_id", "user_id", "union_id"):
        value = sender.get(key)
        if isinstance(value, str) and value:
            return value

    return None
