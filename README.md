# Home Assistant Feishu Bot Integration

通过飞书官方 WebSocket 通道接收机器人消息，并将命令映射到 Home Assistant 服务调用。

## 功能

- WebSocket 接收飞书机器人消息（`im.message.receive_v1`）
- 命令式控制 Home Assistant：
  - `ha:service <domain.service> {json}`
  - `ha:state <entity_id>`
  - `ha:scene <scene_id>`
- 白名单服务域控制（默认 `light,switch,script,scene`）
- 执行结果回传飞书会话

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

## 命令示例

```text
ha:service light.turn_on {"entity_id":"light.living_room","brightness":180}
ha:state sensor.living_room_temperature
ha:scene scene.good_night
```

## 注意事项

- 建议在飞书应用权限里只开通必要权限。
- 建议限制允许调用的 HA 服务域，避免误操作。
- 该版本为首版，后续将补充更完整的 diagnostics 与 repair 流程。
