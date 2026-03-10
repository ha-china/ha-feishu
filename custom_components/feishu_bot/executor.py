"""Command executor for Home Assistant actions."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any

from homeassistant.core import Context
from homeassistant.core import HomeAssistant


@dataclass(slots=True)
class Command:
    kind: str
    target: str
    payload: dict


class HomeAssistantCommandExecutor:
    """Executes parsed commands against Home Assistant."""

    def __init__(self, hass: HomeAssistant, agent_id: str | None) -> None:
        self._hass = hass
        self._agent_id = agent_id

    async def async_execute(self, command: Command) -> str:
        if command.kind == "conversation":
            return await self._async_execute_conversation(command)

        if command.kind == "service":
            return await self._async_execute_service(command)

        if command.kind == "state":
            state = self._hass.states.get(command.target)
            if state is None:
                return f"未找到实体: {command.target}"
            return f"{command.target} 当前状态: {state.state}"

        if command.kind == "scene":
            await self._hass.services.async_call(
                "scene",
                "turn_on",
                {"entity_id": command.target},
                blocking=True,
            )
            return f"已执行场景: {command.target}"

        return "不支持的命令类型"

    async def _async_execute_service(self, command: Command) -> str:
        if "." not in command.target:
            return "服务格式错误，应为 domain.service"

        domain, service = command.target.split(".", 1)
        await self._hass.services.async_call(domain, service, command.payload, blocking=True)
        payload_text = json.dumps(command.payload, ensure_ascii=False) if command.payload else "{}"
        return f"已执行服务: {domain}.{service} 参数: {payload_text}"

    async def _async_execute_conversation(self, command: Command) -> str:
        """Delegate free text to Home Assistant conversation agent."""
        conversation_id = str(command.payload.get("conversation_id") or "")
        reply = await _ask_home_assistant(
            self._hass,
            command.target,
            conversation_id=conversation_id,
            agent_id=self._agent_id,
        )
        return reply or "对话已处理，但没有可显示的回复"


async def _ask_home_assistant(
    hass: HomeAssistant,
    text: str,
    *,
    conversation_id: str,
    agent_id: str | None,
) -> str:
    """Route text through Home Assistant conversation agent."""
    try:
        from homeassistant.components import conversation as conversation_component

        if hasattr(conversation_component, "async_converse"):
            signature = inspect.signature(conversation_component.async_converse)
            kwargs: dict[str, Any] = {}
            if "hass" in signature.parameters:
                kwargs["hass"] = hass
            if "text" in signature.parameters:
                kwargs["text"] = text
            if "conversation_id" in signature.parameters and conversation_id:
                kwargs["conversation_id"] = conversation_id
            if "context" in signature.parameters:
                kwargs["context"] = Context()
            if "language" in signature.parameters:
                kwargs["language"] = hass.config.language
            if "agent_id" in signature.parameters and agent_id:
                kwargs["agent_id"] = agent_id

            result = await conversation_component.async_converse(**kwargs)
            speech = _extract_speech_any(result)
            if speech:
                return speech
    except Exception:  # noqa: BLE001
        pass

    data: dict[str, Any] = {
        "text": text,
        "language": hass.config.language,
    }
    if conversation_id:
        data["conversation_id"] = conversation_id
    if agent_id:
        data["agent_id"] = agent_id

    response = await hass.services.async_call(
        "conversation",
        "process",
        data,
        blocking=True,
        return_response=True,
    )
    return _extract_speech(response)


def _extract_speech(response: dict[str, Any] | None) -> str:
    if not response:
        return ""
    speech = response.get("response", {}).get("speech", {}).get("plain", {})
    if isinstance(speech, dict):
        value = speech.get("speech")
        return value.strip() if isinstance(value, str) else ""
    if isinstance(speech, str):
        return speech.strip()
    return ""


def _extract_speech_any(response: Any) -> str:
    if isinstance(response, dict):
        return _extract_speech(response)

    text = ""
    try:
        plain = response.response.speech.get("plain", {})
        if isinstance(plain, dict):
            text = plain.get("speech", "")
        elif isinstance(plain, str):
            text = plain
    except Exception:  # noqa: BLE001
        pass

    if isinstance(text, str) and text.strip():
        return text.strip()

    if hasattr(response, "as_dict"):
        try:
            data = response.as_dict()
            if isinstance(data, dict):
                return _extract_speech(data)
        except Exception:  # noqa: BLE001
            pass

    return ""
