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
        reply_target = self._resolve_reply_target(message)
        if reply_target is None:
            _LOGGER.warning("Ignore message %s because receive_id missing", message.message_id)
            return
        receive_id, receive_id_type = reply_target

        _LOGGER.info(
            "Inbound Feishu message id=%s target_type=%s text=%s",
            message.message_id,
            receive_id_type,
            (message.text or "")[:120],
        )

        try:
            command = self._parse_command(message.text)
        except ValueError as err:
            await self._api_client.async_send_safe_reply(
                receive_id=receive_id,
                receive_id_type=receive_id_type,
                text=f"Invalid command: {err}",
            )
            return

        if command is None:
            return

        if command.kind == "conversation":
            command.payload["conversation_id"] = f"feishu:{receive_id}"

        try:
            result = await self._executor.async_execute(command)
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Command execution failed: %s", err)
            result = f"Execution failed: {type(err).__name__}"

        await self._api_client.async_send_safe_reply(
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            text=result,
        )
        _LOGGER.info("Reply sent for message id=%s", message.message_id)

    def _parse_command(self, text: str) -> Command | None:
        text = text.strip()
        if not text:
            return None

        if not text.startswith("ha:"):
            return Command(kind="conversation", target=text, payload={})

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

        raise ValueError("unsupported ha: command")

    def _resolve_reply_target(self, message: IncomingMessage) -> tuple[str, str] | None:
        """Resolve reply receive_id and receive_id_type from message context."""
        if self._reply_receive_id_type == "open_id" and message.user_id:
            return message.user_id, "open_id"

        if message.chat_id:
            return message.chat_id, "chat_id"

        if message.user_id:
            return message.user_id, "open_id"

        return None
