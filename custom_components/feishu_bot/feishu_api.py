"""Feishu HTTP API helpers."""

from __future__ import annotations

import asyncio
import json
import logging
from json import JSONDecodeError

import aiohttp
import lark_oapi as lark
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import REPLY_MAX_LENGTH
from .exceptions import FeishuAuthError

_LOGGER = logging.getLogger(__name__)

_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"


class FeishuApiClient:
    """Wrapper around required Feishu HTTP and SDK APIs."""

    def __init__(self, hass: HomeAssistant, app_id: str, app_secret: str) -> None:
        self._hass = hass
        self._app_id = app_id
        self._app_secret = app_secret
        self._session = async_get_clientsession(hass)

    async def async_validate_connection(self) -> None:
        """Validate credentials.

        Aligned with openclaw-feishu approach: only verify App ID/Secret by
        obtaining tenant access token during config flow. WebSocket runtime
        connection is handled by the WS client itself.
        """
        await self.async_get_tenant_access_token()

    async def async_get_tenant_access_token(self) -> str:
        payload = {"app_id": self._app_id, "app_secret": self._app_secret}
        async with asyncio.timeout(15):
            response = await self._session.post(_TOKEN_URL, json=payload)
        data = await _async_read_json(response)
        if response.status != 200 or data.get("code") != 0:
            raise FeishuAuthError(f"token request failed: {data.get('msg', response.reason)}")

        token = data.get("tenant_access_token")
        if not token:
            raise FeishuAuthError("token request succeeded but token missing")
        return token

    async def async_send_text_message(
        self,
        *,
        receive_id: str,
        text: str,
        receive_id_type: str = "chat_id",
    ) -> None:
        text = text[:REPLY_MAX_LENGTH]
        content = json.dumps({"text": text}, ensure_ascii=False)

        def _send() -> None:
            client = (
                lark.Client.builder()
                .app_id(self._app_id)
                .app_secret(self._app_secret)
                .log_level(lark.LogLevel.INFO)
                .build()
            )
            request = (
                lark.im.v1.CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    lark.im.v1.CreateMessageRequestBody.builder()
                    .receive_id(receive_id)
                    .msg_type("text")
                    .content(content)
                    .build()
                )
                .build()
            )
            response = client.im.v1.message.create(request)
            if not response.success():
                raise FeishuAuthError(
                    f"send message failed code={response.code}, msg={response.msg}, log_id={response.get_log_id()}"
                )

        await self._hass.async_add_executor_job(_send)

    async def async_send_safe_reply(self, *, receive_id: str, text: str, receive_id_type: str = "chat_id") -> None:
        try:
            await self.async_send_text_message(receive_id=receive_id, text=text, receive_id_type=receive_id_type)
        except (FeishuAuthError, aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Failed to send message back to Feishu: %s", err)


async def _async_read_json(response: aiohttp.ClientResponse) -> dict:
    """Read JSON response body with clear error mapping."""
    try:
        data = await response.json(content_type=None)
    except (aiohttp.ContentTypeError, JSONDecodeError) as err:
        body = await response.text()
        data = _parse_json_from_text(body)
        if data is None:
            raise FeishuAuthError(
                f"invalid json response status={response.status} body={body[:200]}"
            ) from err

    if not isinstance(data, dict):
        raise FeishuAuthError(f"invalid response payload type: {type(data).__name__}")
    return data


def _parse_json_from_text(body: str) -> dict | None:
    """Best-effort extraction for responses with noisy wrappers."""
    body = body.strip()
    if not body:
        return None

    try:
        data = json.loads(body)
        return data if isinstance(data, dict) else None
    except JSONDecodeError:
        pass

    start = body.find("{")
    end = body.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        data = json.loads(body[start : end + 1])
    except JSONDecodeError:
        return None

    return data if isinstance(data, dict) else None
