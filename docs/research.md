# 调研记录（2026-09-21）

这是部署前的调研记录，保留当时的版本、源码发现和方案依据。后续实机结果见 [服务器操作记录](server-operations.md)。

## 基线

- cc-connect GitHub Releases API 当日返回的最新正式版为 `v1.5.0`，发布时间 `2026-08-16T15:06:46Z`。
- 阅读的源码 commit 为 `17c61062c2f9ce9bcdd45a2082e491f9743a2770`。不把 main 上更新的 Web UI 或安装行为混入本版。
- 本地可用 Codex CLI 为 `0.145.0`；仅检查 `--version`、`login --help`、`exec --help`、`app-server --help`。这不是选定的服务器版本，也不是 cc-connect 兼容性联调结果。
- 这一轮尚未连接 AutoDL、使用凭证、创建应用或发送消息。它只能确定待验证的方案。

## 当时能确定什么

| 结论 | 证据 | 使用边界 |
|---|---|---|
| 飞书长连接适合没有独立公网 IP 的实例 | 飞书官方文档、上游文档和平台实现 | 仍需出站 API/WebSocket 可达 |
| cc-connect 支持 Codex / Claude Code | 固定版本 agent 实现 | 不等于所有模型和版本组合已通过联调 |
| 可以重复复用机器人凭证 | 飞书官方长连接说明、配置驱动的连接方式 | 多连接随机单点接收，故每个 App ID 单活是本项目要求 |
| Claude API、Codex ChatGPT 是选定的两条认证路线 | 用户选择；对应官方认证说明 | 不再推荐 Codex API 或 Claude 订阅分支 |
| Claude Code 可使用 DeepSeek | DeepSeek 官方接入文档 | 具体模型名和能力随服务更新 |
| DeepSeek 也有 Codex 接入说明 | DeepSeek Codex / Responses 官方说明 | 历史调研项，用户选择后已排除该分支 |
| AutoDL 数据盘不是永久外部备份 | AutoDL 环境说明 | 同地区文件存储也不能冒充任意地区共享 |
| 无卡模式可避免为纯 CLI 占 GPU | AutoDL 官方说明 | 实例仍在线，资源有限；实际是否够用需测试 |

## 从源码发现的部署问题

### 1. Codex 权限语义与示例注释不一致

[`agent/codex/session.go`](https://github.com/chenhg5/cc-connect/blob/17c61062c2f9ce9bcdd45a2082e491f9743a2770/agent/codex/session.go) 的 `buildExecArgs` 显示，`exec` 后端不使用交互审批。

- `suggest` 使用 `read-only` + `approval_policy=never`。
- `auto-edit` 和 `full-auto` 均使用 `workspace-write` + `approval_policy=never`，两者不是“Shell 仍会问”的区别。
- `yolo` 会绕过审批与沙箱。本项目不默认使用。

[`appserver_session.go`](https://github.com/chenhg5/cc-connect/blob/17c61062c2f9ce9bcdd45a2082e491f9743a2770/agent/codex/appserver_session.go) 的 `appServerModeSettings` 则将 `suggest` 映射为 `on-request` + `read-only`，并处理审批响应。模板显式设置 `app_server_url = "stdio://"`，与源码通过标准输入输出交换协议相符。只有真实飞书“批准”和“拒绝”测试后，才能接受这一分支。

### 2. 缺失白名单可能扩大访问

[`config/config.go`](https://github.com/chenhg5/cc-connect/blob/17c61062c2f9ce9bcdd45a2082e491f9743a2770/config/config.go) 把不存在的 `${VAR}` 替换为空字符串，只记录警告。[`core/message.go`](https://github.com/chenhg5/cc-connect/blob/17c61062c2f9ce9bcdd45a2082e491f9743a2770/core/message.go) 的 `AllowList` 将空值与 `*` 视为允许全部。

因此启动脚本在调用 cc-connect 前拒绝空白、通配符和非 open_id 白名单。`admin_from` 保持未配置，上游会阻止 `/shell`、`/dir`、`/upgrade` 等管理命令；这不禁止 agent 在已授权范围内调用它自己的工具。

### 3. 会话恢复依赖哪些文件

[`cmd/cc-connect/main.go`](https://github.com/chenhg5/cc-connect/blob/17c61062c2f9ce9bcdd45a2082e491f9743a2770/cmd/cc-connect/main.go) 的 `sessionStorePath` 由项目名和绝对工作目录哈希生成文件名。只改工作目录就可能使用不同的会话映射。迁移时优先保留项目名、绝对路径和版本，同时迁移 agent 原生会话记录；否则新建会话并从项目文件恢复。

### 4. AutoDL 不能默认按完整 systemd 主机处理

[`daemon/systemd.go`](https://github.com/chenhg5/cc-connect/blob/17c61062c2f9ce9bcdd45a2082e491f9743a2770/daemon/systemd.go) 会检查 systemd 是否实际运行，容器里不满足时应改用 tmux 等方式。用户级 systemd 还涉及 linger。安装 daemon 会捕获环境信息并写服务配置，不能把服务文件当作天然无敏感内容。

### 5. 升级前重新验收

稳定流程需要记录当前通过验收的组合。新版本先测试最小往返、权限、重启与恢复，再更新基线。安全修复与服务端不兼容变化是重新验收的触发条件。

## 官方来源

| 来源 | 支持的内容 |
|---|---|
| [cc-connect v1.5.0 release](https://github.com/chenhg5/cc-connect/releases/tag/v1.5.0) | 正式版、发行资产与校验和 |
| [cc-connect 飞书接入](https://github.com/chenhg5/cc-connect/blob/v1.5.0/docs/feishu.md) | 自建应用、长连接、权限、卡片回调、setup |
| [cc-connect 配置示例](https://github.com/chenhg5/cc-connect/blob/v1.5.0/config.example.toml) | 环境变量、项目、白名单、heartbeat |
| [cc-connect 使用说明](https://github.com/chenhg5/cc-connect/blob/v1.5.0/docs/usage.zh-CN.md) | 会话、定时任务、daemon；Codex 权限以源码修正 |
| [飞书长连接](https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-configure-/request-url-configuration-case) | 出站连接、无需公网回调、集群随机单点投递 |
| [飞书接收消息事件](https://open.feishu.cn/document/server-docs/im-v1/message/events/receive) | 私聊/群聊权限、订阅与重复推送 |
| [飞书获取会话历史消息](https://open.feishu.cn/document/server-docs/im-v1/message/list) | 飞书历史 API 与权限；不等于 agent 上下文 |
| [OpenAI authentication](https://learn.chatgpt.com/docs/auth) | API key、设备码、SSH 回调、登录缓存；已读取完整官方页面 |
| [Claude Code authentication](https://code.claude.com/docs/en/authentication) | 账号、API、setup-token 与认证来源优先级 |
| [Claude Code setup](https://code.claude.com/docs/en/setup) | 安装和版本管理 |
| [DeepSeek 接入 Claude Code](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code) | ANTHROPIC_BASE_URL / AUTH_TOKEN 和模型映射 |
| [DeepSeek Anthropic API](https://api-docs.deepseek.com/zh-cn/guides/anthropic_api/) | 兼容地址、能力差异 |
| [DeepSeek 接入 Codex](https://api-docs.deepseek.com/quick_start/agent_integrations/codex) | Responses 和 models.json 配置 |
| [AutoDL 环境与目录](https://www.autodl.com/docs/env/) | 系统盘、autodl-tmp、autodl-fs 的不同生命周期 |
| [AutoDL 无卡模式](https://backup.autodl.com/docs/save_money/) | 无 GPU 开机选项及其限制 |
| [Mihomo 代理端口](https://wiki.metacubex.one/config/inbound/port/) | HTTP/SOCKS/mixed 监听 |
| [Mihomo 全局配置](https://wiki.metacubex.one/config/general/) | 监听地址、控制器、选择缓存 |
| [Mihomo 服务部署](https://wiki.metacubex.one/startup/service/) | 真正 systemd 主机上的服务方式；不自动适用于 AutoDL 容器 |

阅读来源时，部分网页检索请求超时，DeepSeek 集成文档因此改为直接通过 HTTPS 获取。飞书页面只返回 JavaScript 外壳，正文则从公开前端使用的 `getDocumentDetail` 只读接口获取。上述来源已读取正文，调研阶段没有登录或操作真实应用控制台。

## 第二轮调研关注会话、模型切换和代理

完整讨论见 [会话与认证设计](session-and-auth.md) 与 [代理和恢复](proxy.md)。补充核对了以下实现。

- `core/engine.go` 的 `cmdModel` 保留 agent session ID，保存所选模型后停止旧交互状态；`switchProvider` 清除当前历史及 agent session ID。`/model` 不负责切换 agent 引擎。
- `core/session.go` 的保存快照包含 active 映射、原生 session ID 和历史，但未复制 `ActiveProvider`；不承诺每个历史会话自动恢复对应服务商。
- `config/config.go` 中模型/provider 写回按原始项目名匹配，没有先展开环境变量。原先直接运行仓库模板会导致写回找不到项目。现在生成独立运行配置，只将项目名写成真实值，密钥仍保留占位符；启动不覆盖已有模型选择。此修复有本地脚本测试，后续 Codex `/model` 切换、重启后的配置保留及真实调用已完成 [实机验收](codex-server-validation.md)。
- 所有模板显式 `reset_on_idle_mins = 0`。当前固定源码默认也是 0，部分示例注释却写 30；显式配置避免依赖相互矛盾的默认说明。
- Codex 的模型列表可能来自缓存或内置后备列表；不能将显示条目等同于账号可用模型。

另外参考了两篇社区实操记录，分别是 [huicod 的 AutoDL/Codex 教程](https://huicod.github.io/blog/cursor-autodl-codex/)和 [freemedom 的 AutoDL/Clash 笔记](https://gist.github.com/freemedom/ea74d923aa5040a62b80c6affa4d5473)。前者提供本地 SSH 反向代理思路，后者记录安装包下载困难；本项目选择服务器常驻代理、必要时本地下载后上传。没有照搬未证实的 Codex proxy 字段、TUN 必选结论或第三方一键脚本。
