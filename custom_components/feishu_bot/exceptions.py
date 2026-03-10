"""Custom exceptions for the Feishu Bot integration."""

from __future__ import annotations


class FeishuBotError(Exception):
    """Base exception for Feishu bot integration."""


class FeishuAuthError(FeishuBotError):
    """Raised when authentication with Feishu fails."""


class FeishuConnectionError(FeishuBotError):
    """Raised when websocket connection cannot be established."""
