"""Command executor for Home Assistant actions."""

from __future__ import annotations

import json
from dataclasses import dataclass

from homeassistant.core import HomeAssistant


@dataclass(slots=True)
class Command:
    kind: str
    target: str
    payload: dict


class HomeAssistantCommandExecutor:
    """Executes parsed commands against Home Assistant."""

    def __init__(self, hass: HomeAssistant, allowed_domains: set[str]) -> None:
        self._hass = hass
        self._allowed_domains = allowed_domains

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
        if domain not in self._allowed_domains:
            return f"服务域不在白名单: {domain}"

        await self._hass.services.async_call(domain, service, command.payload, blocking=True)
        payload_text = json.dumps(command.payload, ensure_ascii=False) if command.payload else "{}"
        return f"已执行服务: {domain}.{service} 参数: {payload_text}"

    async def _async_execute_conversation(self, command: Command) -> str:
        """Delegate free text to Home Assistant conversation agent."""
        response = await self._hass.services.async_call(
            "conversation",
            "process",
            {"text": command.target},
            blocking=True,
            return_response=True,
        )

        if not isinstance(response, dict):
            return "对话已提交，但没有返回结果"

        body = response.get("response")
        if not isinstance(body, dict):
            return "对话已提交，但响应格式未知"

        speech = body.get("speech")
        if isinstance(speech, dict):
            plain = speech.get("plain")
            if isinstance(plain, dict):
                text = plain.get("speech")
                if isinstance(text, str) and text.strip():
                    return text.strip()

        card = body.get("card")
        if isinstance(card, dict):
            text = card.get("content")
            if isinstance(text, str) and text.strip():
                return text.strip()

        return "对话已处理，但没有可显示的回复"
