"""Constants for the Feishu Bot integration."""

from __future__ import annotations

DOMAIN = "feishu_bot"

CONF_APP_ID = "app_id"
CONF_APP_SECRET = "app_secret"
CONF_AGENT_ID = "agent_id"
CONF_REPLY_RECEIVE_ID_TYPE = "reply_receive_id_type"

DEFAULT_REPLY_RECEIVE_ID_TYPE = "chat_id"

SERVICE_SEND_TEXT = "send_text"

ATTR_RECEIVE_ID = "receive_id"
ATTR_RECEIVE_ID_TYPE = "receive_id_type"
ATTR_TEXT = "text"

REPLY_MAX_LENGTH = 1800
