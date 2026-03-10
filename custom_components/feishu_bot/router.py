"""Message parsing and command routing."""

from __future__ import annotations

import json
import logging

from .executor import Command, HomeAssistantCommandExecutor
from .feishu_api import FeishuApiClient
from .models import IncomingMessage

_LOGGER = logging.getLogger(__name__)


class CommandRouter:
    """Routes incoming message text to Home Assistant commands."""

    def __init__(
        self,
        *,
        executor: HomeAssistantCommandExecutor,
        api_client: FeishuApiClient,
        reply_receive_id_type: str,
    ) -> None:
        self._executor = executor
        self._api_client = api_client
        self._reply_receive_id_type = reply_receive_id_type

    async def async_handle_message(self, message: IncomingMessage) -> None:
        receive_id = message.chat_id or message.user_id
        if not receive_id:
            _LOGGER.warning("Ignore message %s because receive_id missing", message.message_id)
            return

        try:
            command = self._parse_command(message.text)
        except ValueError as err:
            await self._api_client.async_send_safe_reply(
                receive_id=receive_id,
                receive_id_type=self._reply_receive_id_type,
                text=f"Invalid command: {err}",
            )
            return

        if command is None:
            await self._api_client.async_send_safe_reply(
                receive_id=receive_id,
                receive_id_type=self._reply_receive_id_type,
                text=(
                    "Unknown command. Supported:\n"
                    "1) ha:service <domain.service> {json}\n"
                    "2) ha:state <entity_id>\n"
                    "3) ha:scene <scene_id>"
                ),
            )
            return

        try:
            result = await self._executor.async_execute(command)
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Command execution failed: %s", err)
            result = f"Execution failed: {type(err).__name__}"

        await self._api_client.async_send_safe_reply(
            receive_id=receive_id,
            receive_id_type=self._reply_receive_id_type,
            text=result,
        )

    def _parse_command(self, text: str) -> Command | None:
        text = text.strip()
        if not text:
            return None

        if text.startswith("ha:state "):
            entity_id = text.removeprefix("ha:state ").strip()
            if not entity_id:
                raise ValueError("ha:state needs entity_id")
            return Command(kind="state", target=entity_id, payload={})

        if text.startswith("ha:scene "):
            scene_id = text.removeprefix("ha:scene ").strip()
            if not scene_id:
                raise ValueError("ha:scene needs scene_id")
            return Command(kind="scene", target=scene_id, payload={})

        if text.startswith("ha:service "):
            content = text.removeprefix("ha:service ").strip()
            parts = content.split(" ", 1)
            service = parts[0].strip()
            if not service:
                raise ValueError("ha:service needs domain.service")

            payload = {}
            if len(parts) > 1 and parts[1].strip():
                payload = json.loads(parts[1].strip())
                if not isinstance(payload, dict):
                    raise ValueError("JSON payload must be an object")
            return Command(kind="service", target=service, payload=payload)

        return None
