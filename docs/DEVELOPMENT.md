# Feishu Bot Integration Development Guide

## 1. Goal

Build a Home Assistant custom integration that receives Feishu bot messages through websocket,
executes selected Home Assistant commands, and replies back to Feishu.

## 2. WebSocket Communication Model (Feishu)

1. App uses `app_id` + `app_secret` to authenticate with Feishu.
2. Feishu websocket channel pushes event `im.message.receive_v1`.
3. Integration normalizes event payload (`message_id`, `chat_id`, sender, text).
4. Router parses command and dispatches to executor.
5. Integration sends result to Feishu using `im/v1/message/create`.

Important network note:

- This websocket mode is outbound from Home Assistant to Feishu.
- No public domain, public IP, or inbound callback endpoint is required.
- Public callback address is only needed for HTTP event subscription mode (not implemented in this project).

Reliability controls in this project:

- In-memory message deduplication by `message_id`.
- Background websocket runner task.
- Safe reply path that logs send failures without crashing HA.

## 3. Home Assistant Integration Design

Core files:

- `custom_components/feishu_bot/__init__.py`: setup/unload lifecycle and service registration.
- `custom_components/feishu_bot/config_flow.py`: UI setup flow and credential validation.
- `custom_components/feishu_bot/feishu_ws_client.py`: Feishu websocket lifecycle and event callback.
- `custom_components/feishu_bot/router.py`: command parsing and response routing.
- `custom_components/feishu_bot/executor.py`: HA command execution.
- `custom_components/feishu_bot/feishu_api.py`: Feishu token/ws endpoint checks and send message API.

Supported command grammar (v1):

- `ha:service <domain.service> {json}`
- `ha:state <entity_id>`
- `ha:scene <scene_id>`

Default allowed service domains:

- `light`
- `switch`
- `script`
- `scene`

## 4. Quality Scale Mapping (Current)

Implemented baseline:

- UI config flow (`config_flow`) with connection test.
- Unique configuration by `app_id` (avoid duplicate entries).
- Config entry runtime objects via `entry.runtime_data`.
- Config flow tests scaffold (`tests/components/feishu_bot/test_config_flow.py`).

Planned next steps to move toward Silver:

- Add reauthentication-specific flow UX.
- Add diagnostics endpoint (`diagnostics.py`).
- Increase test coverage for websocket, router, executor error handling.
- Add better availability logging and recovery telemetry.

## 5. HACS Requirements Mapping

Implemented artifacts:

- `hacs.json`
- Integration directory under `custom_components/feishu_bot`
- `manifest.json` with version, docs, issue tracker, codeowner
- Local brand assets in `custom_components/feishu_bot/brand/` (`icon/logo`, dark variants, and `@2x` variants)
- Repository README and CI validation workflow (`.github/workflows/validate.yml`)

Recommended follow-up:

- Add published GitHub release tags.
- Add repository topics required by HACS listing guidance.
- Add PNG brand assets if needed by your release workflow.

## 6. Security Notes

- Restrict allowed service domains in config options.
- Keep secrets in config entries; do not print them in logs.
- Return concise errors to chat users; avoid leaking stack details.
