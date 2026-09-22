# 部署流程

目标：新实例初始化后，在手机飞书上完成可验证的项目操作。第一版范围为个人使用、每个机器人一个活跃实例和一个项目；两种引擎分别部署两个机器人。需要并发管理多个实例时先看架构文档。

当前实机采用原生二进制安装器和独立 Supervisor。需要复现这一组合时，配合 [后台服务步骤](service-setup.md) 使用；下面的 npm、tmux 是可选部署方式，不与 Supervisor 同时启动同一个机器人。

## 0. 输入与完成标准

| 输入 | 获取方式 | 是否每次更换 |
|---|---|---|
| SSH hostname / port / user / identity | 用户提供连接信息或本地 SSH alias | 通常是 |
| 项目 Git URL、revision、工作目录 | 用户指定 | 尽量固定路径 |
| agent 与认证方式 | API → Claude Code；ChatGPT 账号 → Codex | 固定偏好 |
| Mihomo 订阅/节点、配置私密路径 | 用户提供；先验证目标机出口 | 通常可复用 |
| 飞书 App ID / App Secret | 一次性创建应用后保存 | 通常复用 |
| 该应用下用户 open_id | 官方调试工具或上游 setup 的回填值 | 复用同一应用时通常固定 |
| 模型 key 或交互登录 | 私密文件、环境或用户浏览器 | 重新注入/登录 |
| 外部备份位置与任务预算 | 用户指定 | 每个项目明确 |

“完成”必须有：手机收到来自目标目录的正确回复、权限分支验证、SSH 断开后的使用验证、运行方式与恢复回执。安装命令成功不算端到端完成。

## 1. 飞书侧一次性设置

按 [飞书官方长连接说明](https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-configure-/request-url-configuration-case) 和 [cc-connect v1.5.0 飞书文档](https://github.com/chenhg5/cc-connect/blob/v1.5.0/docs/feishu.md) 在开放平台创建自建应用，启用机器人，设置可用范围为本人。使用的是可接收事件的应用机器人，不是只有发送 Webhook 的群自定义机器人。

首次创建机器人也可以用 `cc-connect feishu new` 的扫码入口，自动回填凭证和本应用下的用户 open_id；本项目已用该入口创建 Codex 应用，见 [Codex 实机记录](codex-server-validation.md)。临时配置必须放在私密目录，核验白名单后才启动服务。**更换服务器时复用原应用凭证，不重新扫码创建应用。**

若选择让两个应用具备相同的扩展权限和创建类型，两者都使用上述扫码入口，再按 [飞书权限对齐流程](feishu-permission-preset.md) 比较实际授权清单。该文档也保留了已有应用原地增加权限的可选流程；原地升级不改变应用创建来源或客户端展示类型。

先只做私聊文本链路：申请读取用户发给机器人的单聊消息 `im:message.p2p_msg:readonly` 和发送消息 `im:message:send_as_bot` 所需权限；权限依据[飞书官方接收消息事件](https://open.feishu.cn/document/server-docs/im-v1/message/events/receive)，发送权限以控制台对应 API 要求为准。有额外的元信息或发消息权限错误时按错误码补充。暂不为了单聊开通“读取群内所有消息”。

事件订阅选择“使用长连接接收事件”，添加 `im.message.receive_v1`。部分控制台步骤需要服务端先建立长连接，届时先完成第 2—5 步并前台启动，再返回保存订阅。发布应用版本，核验可用范围和权限已生效。

必须检查“已添加事件”表中实际出现 `im.message.receive_v1`；只看到“长连接”或连接成功不足以证明订阅完成。若该选项灰色，先核对所需消息权限。补齐后重新发送测试消息，不假设旧消息会补投递。

本项目模板默认纯文本回复且不发 reaction，减少初次接入依赖。需要交互卡片时再打开 `enable_feishu_card`，配置长连接回调 `card.action.trigger`，补充控制台要求的卡片权限并重新发布；卡片按钮必须测试批准和拒绝。

可选：上游 `cc-connect feishu setup --project my-project` 提供扫码创建/关联流程，可能回填凭证及白名单，并修改它选中的配置文件。使用前检查该路径是否已有配置，避免影响其他机器人；本项目模板不依赖该自动配置流程。不要把带 App Secret 的 `--app id:secret` 命令保存进历史或文档。

获取本人在**这个应用下**的 `open_id`，用于 `FEISHU_ALLOW_FROM`。用户 ID、邮箱、手机号、另一应用的 open_id 不能混用。白名单确认后，`/whoami` 可用于复核；不得为了获取 ID 长期留空或设为 `*`。

## 2. 新实例只读预检

用用户提供的 SSH alias 进入实例，核验服务器身份与主机指纹。检查：

```bash
uname -sm
id
df -h
ps -p 1 -o comm=
command -v bash git node npm tmux cc-connect codex claude
```

另查已有 bridge、agent 和训练进程，避免重复启动。确认目标项目的实际路径与目录所有权。若要 GPU 实验，再检查 GPU/CUDA；桥接自身不需要 GPU。

需要到 GitHub/软件源、飞书 API 和其协商出的 WebSocket 地址、所选模型及登录服务的出站连接。不要把 WebSocket 目标固定猜成飞书 API 域名；以 SDK 日志中的域名检查。只访问首页获得 HTTP 响应仅能证明有限连通性，模型 smoke test 才能证明调用。

如果网络不满足，记录具体失败层；仅采用用户已授权、符合服务商条件的网络配置，不自动关闭 TLS 校验。

### 2.1 先建立代理出网

按 [代理与开机恢复](proxy.md) 准备服务器 Mihomo、用户提供的配置及专用代理环境。代理不可用时先完成可离线上传的准备，不把安装 CLI 成功当作登录可用。两台机器共用本地 SSH 反向代理只作临时排障，不是本方案持续运行的默认依赖。

## 3. 安装并记录准确版本

先检查是否已安装、是否其他项目在使用。CLI 与桥接应以同一 OS 用户运行，保证读取的是同一份登录状态；不要在 root 登录后换用户启动而不迁移授权。

本项目冻结 `cc-connect@1.5.0`。安装示例使用独立 npm prefix，不替换系统的全局 agent；执行前需已有受所选 CLI 支持的 Node.js/npm：

```bash
npm install --prefix "$HOME/.local/feishu-agent-cli" cc-connect@1.5.0
export PATH="$HOME/.local/feishu-agent-cli/node_modules/.bin:$PATH"
cc-connect --version
```

也可以使用 [正式版发行包](https://github.com/chenhg5/cc-connect/releases/tag/v1.5.0)，按 `uname -m` 选 Linux amd64/arm64 并核对校验和。不要把当前 release 的文件名猜成旧教程的裸二进制下载地址。

agent 版本由已有验收基线决定；没有基线时从官方选择候选版本，记录并在第 6 步验收。例如已设置准确版本变量后：

```bash
# 只执行所选路线。变量应是确切版本号，不是 latest。
: "${AGENT_CLI_VERSION:?请先选定准确的 CLI 版本}"
# Codex:
npm install --prefix "$HOME/.local/feishu-agent-cli" "@openai/codex@$AGENT_CLI_VERSION"
# 或 Claude Code:
# npm install --prefix "$HOME/.local/feishu-agent-cli" "@anthropic-ai/claude-code@$AGENT_CLI_VERSION"
```

Claude Code 也可走官方原生安装器的指定版本安装；记录其自动更新设置。需要冻结候选基线时，在该部署环境设置 `DISABLE_AUTOUPDATER=1`，后续升级显式重新验收。cc-connect 和 agent 是两个独立版本，不只记录一个。

将本项目文件放到服务器上的独立目录，例如 `/root/tools/feishu-agent-bootstrap`。恢复目标项目的 Git revision、依赖和必要文件。不要覆盖已有未提交修改；迁移不是 `git reset --hard`。

## 4. 先单独验证模型登录

### Codex：仅 ChatGPT 账号

在已载入代理环境的服务器 shell 执行 `codex login --device-auth`，用户在自己浏览器中打开官方链接并输入一次性码。设备码功能需要账号/组织允许。成功后执行 `codex login status`，确认使用 ChatGPT 账号；检查本次环境、Codex 配置是否仍有 API key、自定义 provider 或旧 API 登录冲突。只处理目标机对应配置，不改本机其他任务的登录。

设备码不可用时按 [OpenAI 官方 headless 说明](https://learn.chatgpt.com/docs/auth#login-on-headless-devices) 使用 SSH 转发 localhost 登录回调。已存在的 file-based 登录缓存通过 SSH 复制只作为明确确认后的备选；缓存视为密码，绝不进 Git 或公开镜像。设备码不需要公网回调，但仍要服务器能访问认证与模型服务。

在测试 Git 目录执行最小请求：回复随机字符串，再读取已知内容文件。只有登录状态正常而没有实际模型回复，不算通过。

### Claude Code：API 模型

- `claude-anthropic`：用户提供 `CLAUDE_API_KEY` 与 `CLAUDE_MODEL`，模板走官方 Anthropic API。
- `claude-deepseek`：用户提供 `DEEPSEEK_API_KEY` 与 `DEEPSEEK_MODEL`，走 `https://api.deepseek.com/anthropic`。
- 其他 API：先确认服务商 Anthropic Messages 兼容接口、认证头与工具支持，再在私密运行配置中添加 provider；仅 OpenAI 格式的 endpoint 不能直接填入。

这两条 Claude 模板不要求 Claude 订阅登录。先核对并清除当前部署环境中冲突的 OAuth、gateway、Bedrock/Vertex/Foundry 设置；不要修改其他项目的全局环境。单独测试 DeepSeek CLI 的示例：

```bash
(
  unset ANTHROPIC_API_KEY CLAUDE_CODE_OAUTH_TOKEN
  export ANTHROPIC_BASE_URL='https://api.deepseek.com/anthropic'
  export ANTHROPIC_AUTH_TOKEN="$DEEPSEEK_API_KEY"
  export ANTHROPIC_MODEL="$DEEPSEEK_MODEL"
  cd "$PROJECT_DIR"
  claude
)
```

Anthropic 路线在独立 shell 设置 `ANTHROPIC_API_KEY="$CLAUDE_API_KEY"`、官方 endpoint 和所选模型，并清除冲突的 AUTH_TOKEN/OAuth。核验 `/status`、实际 provider、回复、读文件与工具调用。准确模型名用账号可用值，不把某个日期的名称作为永久保证；旧模型别名环境变量和子 agent 的模型覆盖也应检查。

模板使用命名 provider，以支持 `/model` 的配置持久化。额外模型可在运行文件中用 `[[projects.agent.providers.models]]` 的 `model` / `alias` 字段配置；仅加入经过验证的条目。跨 provider 切换前先阅读 [会话与认证设计](session-and-auth.md)。

## 5. 准备环境文件并启动

将 `examples/bridge.env.example` **复制到代码仓库之外**，例如 `~/.config/feishu-agent/bridge.env`。目录 `700`、文件 `600`，由用户在安全编辑器中填写。不在聊天、终端日志、`env`、`ps e` 或命令参数中展示密钥。

`PROJECT_DIR` 应指向已经恢复的项目目录；`BRIDGE_STATE_DIR` 是独立、仅当前用户可访问的状态目录。源仓库的模板只保留 `${VAR}`。首次运行生成 `BRIDGE_STATE_DIR/config.<profile>.toml`：只展开项目名，保留密钥占位符；此后复用，不在重启时覆盖手机选择的模型。已有状态目录必须提前确认为私密目录。

进入本项目根目录，在 Bash 中运行：

```bash
set +x
source "$HOME/.config/feishu-agent/bridge.env"
# 若此部署依赖服务器代理，载入已确认可用的私密 proxy.env：
# source "$HOME/.config/feishu-agent/proxy.env"
export PATH="$HOME/.local/feishu-agent-cli/node_modules/.bin:$PATH"
bash scripts/run-bridge.sh claude-deepseek --check
bash scripts/run-bridge.sh claude-deepseek
```

按所选路线替换 profile。`--check` 会验证必填环境、显式 open_id、目录、CLI 存在及 cc-connect 版本；它不访问飞书、不检测模型 key 有效性，也不证明远程旧节点已停止。环境文件是可信 Bash 脚本，只能 source 本人维护的文件。

模板默认不开管理后台、不启用 `/shell` 等管理命令。若要这些能力，另行配置项目级 `admin_from` 为本人并评估其完整主机权限。`/model` 写入私密运行配置；不得重启时用模板覆盖它。修改权限/provider 后核验实际保存结果，并备份运行配置。切换 profile 使用不同运行文件；升级模板时先备份再做差异合并。

## 6. 前台验收后再后台运行

先前台观察连接成功，在手机私聊机器人发送随机标记，完成 [验收清单](acceptance.md) 的最小测试，再用 Ctrl-C 正常停止前台实例。确认旧进程退出后启动后台，不能前后台各开一个。

AutoDL 容器没有正常 systemd 时，先用独立 tmux session：

```bash
tmux new-session -s feishu-agent
# 在新会话中执行：
cd /root/tools/feishu-agent-bootstrap
set +x
source "$HOME/.config/feishu-agent/bridge.env"
# 若此部署依赖服务器代理，载入已确认可用的私密 proxy.env：
# source "$HOME/.config/feishu-agent/proxy.env"
export PATH="$HOME/.local/feishu-agent-cli/node_modules/.bin:$PATH"
bash scripts/run-bridge.sh claude-deepseek
# 按 Ctrl-b，然后 d，分离会话。
```

不同 OS 用户需要替换示例绝对路径。停止：`tmux attach -t feishu-agent` 后 Ctrl-C，检查已退出。不要误杀训练 session。不要默认使用 `--force` 杀掉未确认归属的 cc-connect 实例。

tmux 只处理断开 SSH，不自动重启崩溃进程。真实 systemd 可用时，可依据上游 daemon 文档配置服务，或将同样的启动入口放入服务管理器。必须显式载入私密环境和完整 PATH，验证用户级服务在退出登录后的存活，以及实际重启。不要把 `.bashrc` 假定为服务的环境来源，也不要同时使用两种守护方式。

### 6.1 开机恢复与手机切换

按 [代理文档](proxy.md) 的顺序先恢复 Mihomo，再启动 bridge。检查 `/current`、`/history`，从 `/list` 中用 `/switch` 选择旧会话，执行同一 session 的续聊测试。`reset_on_idle_mins = 0` 禁用闲置自动换会话。必须完成真实关机开机验收，不能仅重启 tmux 就声称完成。

当前已部署实例的开机钩子执行 `scripts/start-after-boot.sh`，包含启动顺序、互斥锁和有限重试。新服务器接入前先核对平台真实启动入口并保留已有脚本；具体安装与验证边界见 [重启与自启记录](server-operations.md#重启与自启的当前状态)。

在飞书发送 `/model` 查看模型，`/model switch <名称>` 切模型；等待当前轮完成后操作。`/provider switch` 将创建新的原生会话上下文，不作为无缝模型切换。两个引擎通过两个机器人窗口切换；两条流程各自验收。

## 7. 让项目持续推进

给项目补充 `TASKS.md`（目标与当前最小任务）和 `STATE.md`（已验证进度与恢复入口）；示例只追加/合并，不覆盖项目已有约定。每个实质任务结束更新状态。

长训练由独立 tmux / 作业调度器启动，分配唯一任务 ID，记录启动命令、PID/session、stdout/stderr、退出码和 checkpoint。agent 短时间检查日志与产物，然后返回飞书；不把几小时训练绑在一次模型工具调用上。结束消息要区分“进程结束”和“结果通过验收”。

需要周期检查时才启用上游 heartbeat：固定项目与实际 session_key、空闲时执行、明确每轮上限、只在完成/失败/需要用户处理时通知。`silent` 只是不发送启动提示，不代表业务回复全部静默；提示词需要说明通知条件。heartbeat 的配置字段见固定版本 config.example.toml；用 `/heartbeat`、`/heartbeat pause`、`/heartbeat run` 核验状态和实际行为。不要猜测 session_key，使用当前版本实际提供的会话信息，且不要公开含用户内容的日志。

## 8. 部署回执

在私有记录中写入：日期、实例脱敏标识、项目 revision、cc-connect 和 agent 准确版本、模型/provider、认证类别、profile、工作/状态目录、进程管理方式、各验收项结果、备份位置、下一步。无凭证时只交付准备状态，不标记真实部署完成。
