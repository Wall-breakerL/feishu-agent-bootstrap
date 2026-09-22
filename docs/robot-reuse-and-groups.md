# 机器人换机与群聊共用

换服务器可以沿用已有机器人，群聊也可以开放给获准成员。本页说明两种情况分别要改什么，并记录 2026-09-22 两个机器人在群里协作的测试。实现依据为 cc-connect v1.5.0 和飞书官方文档。

## 换服务器可以继续用同一个机器人

飞书应用身份由 App ID / App Secret 确定，不绑定 AutoDL 的 SSH 地址。新服务器使用相同应用凭证建立出站长连接即可接管，通常不必重新创建应用、加好友或更换飞书聊天窗口。

按下面的顺序接管，避免新旧服务器同时收消息。

1. 在旧机器停止接收新任务，记录当前项目和实验状态。
2. 准备新机器的工具、代理、项目目录和模型认证，暂不连接生产机器人。
3. 停止旧 cc-connect，确认它已退出。
4. 保存最后的 bridge 状态和 agent 原生会话，连同运行配置迁至新机器；尽量保持相同项目名、绝对工作目录、OS 用户和版本。
5. 注入相同飞书凭证与白名单，启动新 bridge，在手机验收项目身份、会话 ID 与上下文。

只搬应用凭证就能恢复机器人收发，但想延续模型原会话，还要迁移本地记录。飞书已有消息与 agent 上下文分别保存。Codex 账号状态可以在新机重新授权；没有完整状态时用项目 STATE 交接并明确标记新会话。

**一个 App ID 保持一个活跃接收节点。** 飞书官方说明，同一应用的多个长连接客户端是集群接收模式，一个事件只随机交给其中一个客户端；不会按服务器项目自动分流。详见[飞书长连接](https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-configure-/request-url-configuration-case)。

## 多人可以通过群聊共用

同一飞书组织内，可以按下面的步骤开放协作。

1. 将应用可用范围扩展到需要协作的人，并按组织规则发布/审核。
2. 在应用权限中增加 `im:message.group_at_msg:readonly`（接收群聊中用户 @ 机器人消息）；保留 `im.message.receive_v1` 事件和发送权限，重新发布。
3. 将机器人添加到目标群。
4. 将允许操作的每个人在**这个应用下**的 open_id 加入 `FEISHU_ALLOW_FROM`，逗号分隔；重启 bridge 载入更新。
5. 保持 `group_reply_all = false`，群里通过 @ 机器人发任务。

私聊权限和群聊权限需要分别申请；只做 @ 场景不需要读取所有群消息。具体要求见 [飞书接收消息事件](https://open.feishu.cn/document/server-docs/im-v1/message/events/receive)。跨组织/外部群还需核对应用可用范围和平台支持，不能直接套用内部群的结论。

## 群里的上下文安排

| 配置 | 实际会话边界 | 适用方式 |
|---|---|---|
| `share_session_in_channel = false`（默认） | 群 ID + 发言人 ID | 每位成员各聊各的历史 |
| `share_session_in_channel = true` | 群 ID | 群内获准成员接着同一段对话讨论 |
| `thread_isolation = true` | 群 ID + 话题根消息 ID | 按群话题区分任务；本次机器人协作采用并通过单话题往返验收 |

会话键的生成方式见 [Feishu makeSessionKey](https://github.com/chenhg5/cc-connect/blob/v1.5.0/platform/feishu/feishu.go)。无论选择哪种会话模式，同一个 cc-connect project 默认都使用同一工作目录、服务器执行身份和模型账号；成员的文件操作与费用会影响共同项目。需要独立权限和文件环境时，为成员或项目拆分部署。

个人私聊、群聊和不同群的会话不会仅因“同一个机器人”而自动合并。`thread_isolation` 在群话题中优先使用根消息 ID，因此同一话题的人类发起消息和对端机器人回报可以续接同一个 agent 会话。两个 agent 各自保留原生历史，通过发给对方的消息交换信息；它们不会自动共享全部私聊、文件或隐藏上下文。

## 已验证的 Codex 与 CC 群内协作

2026-09-22 已建立私有测试群「Agent 协作测试｜Codex × CC」，成员为用户本人及两个机器人。采用飞书原生机器人 @ 消息，两条 bridge 仍独立运行。单话题往返已通过，其他用户加入、多人共享上下文、跨话题隔离仍待专项验收。

### 接入步骤

1. 两个应用都订阅 `im.message.receive_v1`，具备发送消息、接收用户群 @ 消息及 `im:message.group_at_msg.include_bot:readonly` 权限；发布后重新连接。本次沿用扫码创建应用已有权限，没有增加读取全部群消息的权限。
2. 创建群并添加两个机器人。本次通过一个应用的 API 邀请另一个机器人返回 `Bot is not allowed to be invited by other app`，由群主在飞书「添加机器人」中完成。
3. 获取各机器人自身身份，用于生成出站 @。再让双方在测试群互相发送一次 @ 探针，从接收端事件核对 `sender_type=bot`、消息 ID 和实际 `sender_id.open_id`。**对端接收到的 sender open_id 可能不同于机器人查询自身信息得到的 open_id，不能混用。** 只将与已知探针对应的身份加入白名单。
4. 每条 bridge 的 `FEISHU_ALLOW_FROM` 仅加入本人及已核实的对端 sender ID；`FEISHU_TEST_CHAT_ID` 指定测试群；`FEISHU_PEER_BOT_ID` 使用出站 @ 所需的对端机器人自身 open_id。私密值保存在各自 env 文件中。
5. 在每条实际运行配置的 `[projects.platforms.options]` 中加入以下配置。Codex 使用 `ServerCC`，CC 侧将这个键换成 `ServerCodex`。

```toml
group_reply_all = false
enable_feishu_card = true
allow_chat = "${FEISHU_TEST_CHAT_ID}"
thread_isolation = true
resolve_mentions = true
mention_map = { "ServerCC" = "${FEISHU_PEER_BOT_ID}" }
```

6. 在 `[display]` 中设置 `thinking_messages = false`、`tool_messages = true`，避免计划预览里的提及意外触发对端，保留工具过程提示。给两边的 `append_system_prompt` 加入下述协作约定，备份后重启 bridge，再做实际消息验收。

### 协作约定与使用方式

每个任务使用唯一任务编号；派工和回报都放在原话题中。Codex 最终派工消息以 `@ServerCC` 开头，CC 最终回报以 `@ServerCodex` 开头；别名会被转换为真正的飞书提及。仅在明确派工或回报时提及对端，思考、工具说明和引用中不要提及。收到完成回报后，Codex 验收并向用户报告，结束时不再提及机器人。每个任务约定最多一次派工和一次回报；这是提示词约定，尚未实现程序层面的轮数上限。

用户发起任务时，在飞书输入框选择真正的 `@Server Codex`，要求它把具体任务交给 CC 并等待回报。若 CC 请求工具权限，在**同一话题**中 `@Server CC` 回复「允许」或「拒绝」；本次使用单次允许，没有选择允许所有。API 派工不绕过原有工具审批，涉及待批操作时仍需人介入。

### 消息排版与报告交付

cc-connect v1.5.0 会把含真实提及的整条消息转成普通文本，以便触发对端机器人。即使开启卡片，夹在这条消息中的 Markdown 也不会自动变成卡片排版。没有提及的 Markdown 回复通常使用卡片，超过当前卡片表格数量限制时回退到富文本。[发送类型选择源码](https://github.com/chenhg5/cc-connect/blob/v1.5.0/platform/feishu/feishu.go#L3090)

两条路线采用下面的交付约定。

| 内容 | 发送方式 |
|---|---|
| 普通问答 | 直接返回不含机器人提及的 Markdown，由桥接渲染 |
| 长报告 | 按任务允许的产物范围保存 `.md`，发送附件及不含提及的摘要 |
| 派工、回报 | 在最终回复中只发简短的真实提及、任务编号、必要范围或结果、报告绝对路径 |
| 最终验收 | 向用户说明结果，结束时不再提及机器人 |

需要同时交付报告和回报对端时，agent 在当前会话调用 `cc-connect send --file /实际绝对路径/report.md --message '不含提及的 Markdown 摘要'`，成功后再用最终回复发送简短通知。这会把摘要和附件分别发出；最终的提及消息负责触发另一个机器人。路径和摘要使用实际内容，复杂文本需正确处理 shell 引用。保留 bridge 注入的 `CC_PROJECT`、`CC_SESSION_KEY` 和 `CC_DATA_DIR`，不另选群或会话。附件发送失败时如实报告，不声称已经送达。[上游附件说明](https://github.com/chenhg5/cc-connect/blob/v1.5.0/docs/usage.md)

当前两个 agent 共用服务器，可以按绝对路径读取同一份报告；不能假定对端能读到上一张卡片或完整群历史。换到不同服务器时，需先提供双方确实可访问的文件或授权链接。任务禁止写文件或工具仍待审批时，先遵守该限制，不为排版自动放开权限。

四份配置模板的 `append_system_prompt` 均包含 `FEISHU_MESSAGE_FORMAT_V1` 回复约定，默认启用卡片。升级已有部署时，需把约定追加到两份私密运行配置，保留各自已有的对端别名、任务轮数、模型及审批规则；只更新仓库模板不会覆盖运行配置。检查没有正在执行或待审批的任务后，备份运行配置，再分别重启 bridge。卡片回调还需在应用发布版本中包含 `card.action.trigger`。

这是配置与提示词约定，尚未改成程序强制拆分消息；模型若把提及和长报告混在同一条回复中，仍会触发纯文本路径。手机端需按 [A16](acceptance.md) 验收标题、列表、代码块、表格、附件和机器人回报，并另测审批按钮。卡片不能保证完整复现 GitHub 的所有 Markdown 扩展。

这次选择飞书原生 @ 消息，是为了在两个独立 bridge 之间传递任务，并保留原有审批。`cc-connect relay` 在 v1.5.0 中使用单进程内的 agent 注册表，`HandleRelay` 还会自动批准收到的工具权限请求，因此没有采用。[上游实现](https://github.com/chenhg5/cc-connect/blob/v1.5.0/core/engine.go)

### 验收结果与边界

- 用户群消息触发 Codex，Codex 原生记录两轮均为 `gpt-6-astra`、`high`；两轮均未调用工具。
- CC 收到真实机器人 @ 后读取测试 CSV，原生记录为 `deepseek-flash`、`high`；一次只读统计命令经群话题内单次批准后执行。
- CC 返回 5 笔 paid 订单，分类金额 200、50、12，总额 262，以及只存在于文件中的随机验收标记；Codex 在原会话核对结果，输出 `A2A_ROUNDTRIP_DONE`，没有继续派工。
- 两边 bridge 使用相同话题根 ID，各自保存独立原生会话。审批及结果在飞书客户端可见。
- 测试群尚未开放给其他人。多人发言时的上下文续接、跨话题隔离和长时间自主协作，都留待后续测试。当前结果只覆盖一次派工与回报。
- 获取群历史的 REST API 在当前权限下返回缺少 `im:message.group_msg`；本次用实时事件、客户端及服务器原生记录完成核验，没有为测试扩大权限。
