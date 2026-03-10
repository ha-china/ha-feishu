"""Data models for Feishu Bot integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(slots=True)
class IncomingMessage:
    """Normalized incoming message from Feishu."""

    message_id: str
    chat_id: str | None
    user_id: str | None
    text: str


@dataclass(slots=True)
class RuntimeData:
    """Runtime objects stored in config entry."""

    ws_client: object
    api_client: object
    message_handler: Callable[[IncomingMessage], Awaitable[None]]
