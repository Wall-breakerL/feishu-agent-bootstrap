# 会话保留、手机切换与认证设计

手机上的旧消息、服务器保存的会话，以及当前模型选择，分别由不同部分管理。弄清它们存在哪里，才能判断重启或换机后该恢复什么。

本页依据 cc-connect `v1.5.0`（`17c61062c2f9ce9bcdd45a2082e491f9743a2770`）的文档和源码，实机记录更新至 2026-09-22。真实调用、bridge 重启续聊及模型切换的测试结果见 [服务器记录](server-operations.md)。

## 1. 开机后还能继续原来的对话吗？

可以，但前提是磁盘上的状态完整保留，开机后代理和 bridge 正常启动，CLI 也能读取原来的会话。需要保存的记录分为三层。

| 层 | 保存位置 / 作用 | 关机后的条件 |
|---|---|---|
| 飞书聊天记录 | 飞书会话中的消息，可在手机回看 | 服务器关机本身不删除飞书已有消息；仍受飞书侧删除、保留策略影响 |
| cc-connect 会话映射 | `BRIDGE_STATE_DIR` 中保存飞书会话与 agent session 的对应关系、当前会话及简要历史 | 文件保留，项目名、绝对工作目录、应用/用户/聊天身份保持一致 |
| agent 原生对话 | Codex 实际 `CODEX_HOME` 下的会话；Claude Code 的 `~/.claude/projects` 等实际存储 | 同一 OS 用户与有效 home，原生会话和相关配置保留，CLI 支持续接 |

**飞书里看得到旧消息，不等于模型自动获得了旧上下文。** 飞书有[获取会话历史消息 API](https://open.feishu.cn/document/server-docs/im-v1/message/list)，但那是另外的接口和权限；本流程不依赖它重建 agent 原生工具调用历史。

这些行为可以在源码中核对。[`core/session.go`](https://github.com/chenhg5/cc-connect/blob/17c61062c2f9ce9bcdd45a2082e491f9743a2770/core/session.go) 保存会话 ID、agent session ID、历史及 active 映射；[`sessionStorePath`](https://github.com/chenhg5/cc-connect/blob/17c61062c2f9ce9bcdd45a2082e491f9743a2770/cmd/cc-connect/main.go) 用项目名和绝对工作目录哈希定位状态文件；[Codex 会话扫描](https://github.com/chenhg5/cc-connect/blob/17c61062c2f9ce9bcdd45a2082e491f9743a2770/agent/codex/list.go) 还按工作目录过滤。

模板显式设 `reset_on_idle_mins = 0`，禁用闲置后自动换新会话。正常停止优于直接断电；最后一轮尚未落盘的输出、进行中的请求以及内存状态不在保证范围内。认证可能过期，但重新登录和原会话文件是否存在是两件事。

首次验收要实际关机再开机。关机前完成一轮，记录 `/current` 的 session 信息和一个只在聊天里给过的随机标记；开机后核对同一 session，并追问标记。仅“进程又启动了”不算会话恢复通过。换新机器另做迁移验收，不以原机重启代替。

## 2. 飞书里可以切换什么？

| 想做的事 | 手机里操作 | 对原会话的影响 |
|---|---|---|
| 看当前 / 历史会话 | `/current`、`/list`、`/history` | `/history` 是桥接保存的历史视图，不是完整原生工具轨迹 |
| 在多段对话之间切换 | `/switch <序号或 ID 前缀>` | 恢复所选 agent 的已有会话，依赖原生文件 |
| 开一段新对话 | `/new <名称>` | 新建独立会话；旧会话可从列表查找 |
| 同一 provider 内换模型 | `/model`、`/model switch <名称或别名>` | 源码保留 agent session ID；下一轮用新模型续接，实际兼容性要测 |
| 查看 / 切换推理强度 | `/reasoning`、`/reasoning high` | v1.5.0 切换时会清空当前桥接历史、重置原生会话关联；只修改运行时值，不写回默认配置 |
| 在 API 服务商之间切换 | `/provider list`、`/provider switch <名称>` | v1.5.0 会清空当前桥接历史并重置 agent session ID，不是无缝接续 |
| Claude Code 与 Codex 互换 | 第一版切换两个机器人的聊天窗口 | 两套原生历史独立；跨引擎用项目状态文件交接 |

命令行为见 [上游命令说明](https://github.com/chenhg5/cc-connect/blob/v1.5.0/docs/usage.zh-CN.md)与 [`cmdModel` / `switchProvider` 实现](https://github.com/chenhg5/cc-connect/blob/17c61062c2f9ce9bcdd45a2082e491f9743a2770/core/engine.go)。模型选择通常作用于该 cc-connect project 的 agent，不应当作每段对话各自固定的模型配置。切换前等当前轮完成，必要时 `/stop` 并核对副作用。

`/model` 显示的列表可能来自手动配置、服务接口、Codex 本地缓存或内置后备项，不保证账号都能调用；不要为了获取模型列表给 Codex 增加 API key。用实际支持的名称验证一次回复、读文件和工具调用。上下文保留也不表示没有 token 消耗，或者新旧模型的上下文长度及能力一致。

v1.5.0 还有一个需要留意的实现细节。注释写着 provider 会随 session 保存，但保存快照时没有复制 `ActiveProvider` 字段。项目默认 provider 可以写回配置，各段历史会话能否自动找回自己的 provider 则不能据此保证。跨 provider 切换前先更新 STATE，切换后让新会话读取它。

## 3. 两种认证方式分别怎么用

| 路线 | 认证材料 | 建议入口 |
|---|---|---|
| Claude Code → API 模型 | 该服务商 key、Anthropic Messages 兼容 endpoint、有效模型名 | DeepSeek 用 `claude-deepseek`；官方 Anthropic 用 `claude-anthropic` |
| Codex → ChatGPT 账号 | 用户本人完成官方账号授权 | `codex login --device-auth`；先 `codex-readonly`，审批另测 `codex-approval` |

“API 都用 Claude”在这里指 **Claude Code 作为客户端**，不限制后端模型必须来自 Anthropic。但只有 OpenAI Chat Completions/Responses 接口的服务，不能直接套用这套配置，需要该服务商的 Anthropic 兼容入口或另立适配方案。DeepSeek 已有[官方 Claude Code 接入文档](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code)。

Codex 不配置 API provider，也不注入 OpenAI API key。目标机先排除已有 API 登录或自定义 provider 冲突，再完成 ChatGPT 登录；不得动用户本机已有 Codex 登录。按[OpenAI headless 官方说明](https://learn.chatgpt.com/docs/auth#login-on-headless-devices)，设备码能力需要账号/组织允许；不可用时使用官方 SSH localhost 回调方式，登录缓存复制只是经过确认的备选。设备码省去了服务器接收浏览器回调的需求，仍然需要服务器访问认证与模型服务。

Claude API 路线也要检查继承的 OAuth、gateway、Bedrock/Vertex/Foundry 配置。模板设定并不能证明未知机器上没有其他配置覆盖；以目标 CLI 的认证来源和实际请求验收为准。

## 4. 在两个机器人窗口之间切换

第一版建议建 `项目名 · API` 和 `项目名 · Codex` 两个自建应用。前者通过 Claude Code 调 API，后者通过 Codex 使用 ChatGPT 账号。可以先只部署需要的一条，第二条按同样流程增加。

每个机器人有独立 App ID、该应用下的 open_id 白名单、cc-connect project name 和状态目录。本仓库的单项目模板分别启动两个进程即可；每个 App ID 始终单活。同一个仓库若两边都写，使用不同 worktree/分支，或明确串行交接，避免同时改一个目录。

这仍然是在手机飞书内切换，只是切换聊天窗口。若以后要求“一个机器人、一个聊天窗口、一个命令切换两种引擎并继承上下文”，需要另做路由及状态交接功能；当前模板不提供这个承诺。

根据飞书官方说明，长连接只需服务器出站联网，无须公网 IP/域名；同一 App 多个客户端按集群方式随机选一个接收，不广播，也不按项目路由。[飞书长连接文档](https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-configure-/request-url-configuration-case)

## 5. 模型选择必须能写回并跨重启保留

仓库模板里的项目名写成 `name = "${PROJECT_NAME}"`。上游加载配置时会展开变量，但 `SaveAgentModel` / `SaveProviderModel` 写回模型时读取的是原始 TOML，因此无法按真实项目名找到对应项。参见[配置读写实现](https://github.com/chenhg5/cc-connect/blob/17c61062c2f9ce9bcdd45a2082e491f9743a2770/config/config.go)。

启动脚本因此只在首次运行生成 `BRIDGE_STATE_DIR/config.<profile>.toml`，将项目名写成字面量，密钥仍为环境变量占位符。后续重启复用该文件，使 `/model` 的配置修改保留；启动检查根据现有配置验证其引用的变量。运行文件必须可写，源仓库模板保持不变。

更换 profile 会使用另一份配置；从只读升级到审批路线时，停旧进程并检查/迁移选定模型，不把它当作原文件自动升级。模板升级也不覆盖已有运行文件。运行配置与状态一起私密备份，不在手机聊天中用 `/provider add` 粘贴 API key。

## 6. 固定默认推理强度

2026-09-22 按用户选择，将 `claude-deepseek` 与 `codex-approval` 的模板及目标机运行 TOML 都设为 `high`。

```toml
[projects.agent.options]
reasoning_effort = "high"
```

cc-connect 会将这个值传给客户端。Claude Code 接收 `--effort high`；Codex app-server 接收 `model_reasoning_effort="high"`，并用于后续 turn。模型和工具审批模式保持原值。

修改后，两个 bridge 已重启，运行配置也保留了 `high`。群聊派工的原生记录显示，Claude Code 使用 `deepseek-flash`、`effort: high`，Codex 两轮均使用 `gpt-6-astra`、`reasoning_effort: high`。这些记录能确认客户端发出的设置，无法据此判断第三方模型内部具体用了多少推理预算。

若已有运行配置，不能只改仓库模板；需要备份并修改实际 `BRIDGE_STATE_DIR/config.<profile>.toml`，再等当前任务结束后重启。日常 `/reasoning` 不带参数只查询，不会切换会话；`/reasoning high` 是会清空当前会话关联的切换命令，不能用来做无副作用查询。
