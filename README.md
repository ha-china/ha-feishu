# Home Assistant Feishu Bot Integration

通过飞书官方 WebSocket 通道接收机器人消息，并将命令映射到 Home Assistant 服务调用。

## 功能

- WebSocket 接收飞书机器人消息（`im.message.receive_v1`）
- 默认将自然语言交给 Home Assistant `conversation` agent 处理并回复
- 兼容命令式控制 Home Assistant：
  - `ha:service <domain.service> {json}`
  - `ha:state <entity_id>`
  - `ha:scene <scene_id>`
- 白名单服务域控制（默认 `light,switch,script,scene`）
- 执行结果回传飞书会话
- 提供诊断实体 `sensor.feishu_bot_status` 展示连接状态

## 安装

## 网络要求

- 本集成使用飞书 WebSocket 主动外连模式，**不需要公网 IP、端口映射或自有域名**。
- 只要 Home Assistant 所在环境可以主动访问飞书开放平台即可。
- 仅在你选择 HTTP 回调订阅方案时，才会需要可被飞书访问的公网地址。

### HACS（推荐）

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ha-china&repository=ha-feishu&category=integration)

一键安装链接：

```text
https://my.home-assistant.io/redirect/hacs_repository/?owner=ha-china&repository=ha-feishu&category=integration
```

1. HACS -> Integrations -> Custom repositories
2. 添加仓库 `https://github.com/ha-china/ha-feishu`，类别选择 Integration
3. 搜索并安装 `Feishu Bot`
4. 重启 Home Assistant

### 手动安装

将 `custom_components/feishu_bot` 复制到你的 HA 配置目录下。

## 配置

在 Home Assistant 界面中：

1. Settings -> Devices & Services -> Add Integration
2. 搜索 `Feishu Bot`
3. 填入：
   - `App ID`
   - `App Secret`

本集成不提供 HTTP 回调能力，也不需要配置回调 token/encrypt key。

为保持配置简单，当前默认使用内置安全白名单服务域：`light`、`switch`、`script`、`scene`。

## 飞书端操作步骤（WebSocket）

以下流程参考（并适配）OpenClaw 的飞书配置文档：
`https://docs.openclaw.ai/channels/feishu`

1. 在飞书开放平台创建企业自建应用：
   - `https://open.feishu.cn/app`
2. 在“凭证与基础信息”复制：
   - `App ID`
   - `App Secret`
3. 在“权限管理”添加机器人消息相关权限（至少确保可收消息和 `send_as_bot`）。
4. 在“应用能力”启用机器人能力。
5. 在“事件订阅”中选择：
   - 使用长连接接收事件（WebSocket）
   - 添加事件：`im.message.receive_v1`
6. 发布应用版本并在企业内可用。

示例权限导入（可按需精简）：

```json
{
  "scopes": {
    "tenant": [
      "im:message:readonly",
      "im:message:send_as_bot",
      "im:chat.members:bot_access",
      "im:resource"
    ]
  }
}
```

参考截图：

![创建应用](https://mintcdn.com/clawdhub/6NERQ7Dymau_gJ4k/images/feishu-step2-create-app.png)
![获取凭据](https://mintcdn.com/clawdhub/6NERQ7Dymau_gJ4k/images/feishu-step3-credentials.png)
![事件订阅-WebSocket](https://mintcdn.com/clawdhub/6NERQ7Dymau_gJ4k/images/feishu-step6-event-subscription.png)

## 命令示例

```text
打开客厅灯
现在家里温度是多少
把客厅灯调到暖光

# 可选：仍支持显式 HA 命令
ha:service light.turn_on {"entity_id":"light.living_room","brightness":180}
ha:state sensor.living_room_temperature
ha:scene scene.good_night
```

## 注意事项

- 建议在飞书应用权限里只开通必要权限。
- 建议限制允许调用的 HA 服务域，避免误操作。
- 该版本为首版，后续将补充更完整的 diagnostics 与 repair 流程。
