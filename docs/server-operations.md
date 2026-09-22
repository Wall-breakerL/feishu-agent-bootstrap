# 已部署服务器的操作入口

这次部署完成于 2026-09-22，使用一台 Ubuntu 22.04 / x86_64 AutoDL 容器。本页记录实际安装结果、日常命令，以及重启故障的原因和修复。服务器身份、凭证和具体会话信息保存在仓库之外的私有回执中。

## 实际安装与检查

| 项目 | 结果 |
|---|---|
| cc-connect | 1.5.0 / 17c61062，原生二进制版本检查通过 |
| Codex | 0.155.1，ChatGPT 设备码账号登录通过；实际模型 gpt-6-astra；CLI 与飞书读文件、bridge 重启后原会话续聊通过 |
| Claude Code | 2.1.278，DeepSeek Flash 真实调用、Read 工具读取随机文件通过 |
| Claude 原生会话恢复 | 结束第一进程后，新进程 `--resume` 同一会话；禁用工具后正确复述前轮标记 |
| Mihomo | 1.19.31；已迁入本机节点快照；服务器经代理访问 Google 返回 HTTP 200 |
| 飞书 | 手机发消息 → Claude Code / DeepSeek Flash 读取验收文件 → 飞书显示正确标记，完整往返通过 |
| bridge 会话恢复 | 停止并启动 API bridge 后载入同一原生会话 ID，续聊正确；后续一轮 tools=0 复述历史标记与暗号 |
| Supervisor | 使用现有 4.2.5，独立 socket、PID、日志及配置；api / codex / mihomo RUNNING |
| 预检 | 原有 16 项离线测试在目标机通过；缺失代理、飞书凭证时启动入口拒绝启动 |
| 安装器 | 官方资产校验通过；本地额外验证拒绝路径穿越、符号链接和校验不匹配 |

初期临时 direct 模式只验证了 HTTPS 转发；后续已迁入真实节点，并通过 Google 实测。Codex 账号登录与工具调用随后分别完成实测，详见 [Codex 记录](codex-server-validation.md)。

随后按用户要求，将手动创建的 Server CC 替换为与 Server Codex 相同扫码流程创建的智能体应用。两者实际授权集合一致（35 项应用权限 + 1 项用户权限）；原项目和 Claude 原生会话保留，新入口的历史暗号与新文件读取验收通过。旧应用已删除并由认证接口确认失效，见 [应用重建记录](feishu-permission-preset.md#2026-09-22-实机结果)。

两条路线的测试进度有所不同。Codex 已验证飞书中的单次允许与拒绝，并检查了文件是否按预期产生；手机切换模型、保存选择和重启后继续调用也已通过。Claude Code 已在群内批准过一次只读命令，拒绝操作、写入审批与模型切换还没有专项测试。

用户重启实例后，我们检查了配置和会话文件并手动恢复服务。随后补上的开机钩子能从服务全部停止的状态恢复，但修复后的整机开机和换机迁移还没有验收。Codex 当前使用 app-server 逐次审批；容器的 namespace 限制及 Landlock 兼容情况见 [Codex 记录](codex-server-validation.md#autodl-沙箱兼容性)，full-auto 尚不可据此视为可用。

## 目录

```text
/root/tools/feishu-agent-bootstrap/          本项目源码与脚本
/root/.local/opt/feishu-agent/               固定版本工具、下载缓存、installed.json
/root/.config/feishu-agent/deployment.env    目录与 Supervisor 路径
/root/.config/feishu-agent/api.env           DeepSeek 与 API 机器人私密配置
/root/.config/feishu-agent/codex.env         Codex 机器人私密配置
/root/.config/feishu-agent/proxy.env         仅此部署使用的代理环境
/root/.config/feishu-agent/mihomo/           迁入的私密 config.yaml 节点快照
/root/.config/feishu-agent/supervisord.conf  独立进程管理配置
/root/.local/state/feishu-agent/             bridge 状态、运行 TOML、私密日志
/root/autodl-tmp/feishu-agent-demo/api/      独立 API 验收 Git 目录
/root/autodl-tmp/feishu-agent-demo/codex/    独立 Codex 验收 Git 目录
```

未修改系统 shell 配置、现有项目、平台 Supervisor 配置。工具使用隔离的原生二进制目录，没有安装全局 Node/npm。Claude 自动更新在该启动器环境中关闭，避免未经验证改变组合。下载缓存及安装合计约 960 MiB。

## 日常命令

```bash
cd /root/tools/feishu-agent-bootstrap
bash scripts/agentctl.sh status

# api.env 已填好；飞书接收事件需另在控制台核验：
bash scripts/agentctl.sh check api
bash scripts/agentctl.sh start api
bash scripts/agentctl.sh stop api

# Mihomo 配置已迁入：
bash scripts/agentctl.sh check mihomo
bash scripts/agentctl.sh start mihomo
# 仅首次登录或认证失效时运行，已登录无需重复：
bash scripts/agentctl.sh login codex
# 当前 Codex 账号与独立应用均已配置：
bash scripts/agentctl.sh check codex
bash scripts/agentctl.sh start codex
```

`agentctl.sh start` 先检查目标配置，条件满足后才按需启动独立 Supervisor。日志保存在私密状态目录，由 Supervisor 轮转。Mihomo 配置检查可能输出订阅地址，详情也只写入私密日志。

DeepSeek API 进程当前走直连，`api.env` 中 `USE_SERVER_PROXY=0`；Codex 为 1，使用回环代理端口 7890。后续实际网络变化时修改私密配置并重新验证，不影响其他训练进程。

## 重启与自启的当前状态

2026-09-22，用户在 11 时 07 分重启实例，两个机器人随后都没有回复。检查发现，平台 Supervisor 还在运行，本项目的独立 Supervisor、Mihomo 和两条 bridge 却都没有启动，磁盘上的独立 socket 只是上次运行留下的文件。

原因在启动方式。之前设置的 `autorestart=true`，只能让仍在运行的 Supervisor 重启退出的子进程。容器重启后，必须先有人启动这个 Supervisor，再启动三个设置为 `autostart=false` 的服务。此前缺少的就是这个开机入口。

本机 PID 1 是 `bash /init/boot/boot.sh`。实际保留的平台包装脚本 `/init/bin/customer.cmd.sh` 执行 `bash /etc/autodl.sh`；本次开机的 `/tmp/autodl.sh.log` 明确记录该文件不存在。这是本实例的现场证据，不假定所有 AutoDL 镜像都有相同入口。

为此补上了 `/etc/autodl.sh`，调用仓库里的启动脚本。

```bash
#!/bin/bash
exec /bin/bash /root/tools/feishu-agent-bootstrap/scripts/start-after-boot.sh
```

新脚本显式载入部署配置，不依赖 `.bashrc` 或已激活的 Conda；按 Mihomo → API → Codex 顺序启动，单项失败最多重试 3 次，每次命令超时 45 秒。API 路线即使代理启动失败也会单独尝试。`flock --close` 避免并发启动及后台进程继承启动锁；`agentctl` 对已运行的服务不再拉起副本。业务 program 保留 `autostart=false`，由此脚本负责顺序启动，随后 Supervisor 负责运行期重启。没有修改平台 Supervisor、Jupyter 或 SSH。

修复后做了以下检查。

- 用户这次真实重启后，模型认证、运行配置、群聊及私聊会话文件仍在；群聊原生会话 ID 保留，默认推理仍为 high。
- 先人工恢复代理与两个 bridge；Google 经代理 HTTP 200，两条飞书长连接成功。
- 在 agent 空闲时停止本项目独立 Supervisor 及三个服务，使用仅有 HOME/PATH 的环境执行平台包装脚本；三个服务均启动成功。
- 再执行一次钩子，三个进程 PID 不变；这两次启动前后的 bridge 会话文件 SHA256 完全一致。
- 飞书真实消息分别得到 `CODEX_REBOOT_OK`、`CC_REBOOT_OK`，模型仍为 gpt-6-astra / deepseek-flash，均为 high。

**修复后尚未再次重启整台实例**，因此当前证据为“平台入口与停止状态恢复测试通过”，下一次真实开机仍需核验自动触发。没有测试换机。失败时检查 `/root/.local/state/feishu-agent/logs/boot-start.log`；也可手动执行 `bash /etc/autodl.sh`。新实例应先核对自身开机机制，保留已有钩子内容后再接入；不要盲目覆盖 `/etc/autodl.sh`。平台 Pro API 的 `start_command` 是另一种入口，与弹性部署的生命周期语义不同，参见 [AutoDL 官方说明](https://www.autodl.com/docs/instance_pro_api/)。

## 以后重建工具环境

目标机已有 Python 3.11+ 时，可以运行下面的安装命令。

```bash
/root/miniconda3/bin/python scripts/install-linux.py
```

这是针对 Linux x86_64 的固定资产清单，安装在独立目录；它不安装凭证、不创建飞书应用、不启动服务。下载内容先核验固定摘要，解包拒绝路径逃逸和链接。目标机 GitHub 下载慢时，可在能访问官方源的电脑下载同一资产并核验，再上传到安装目录的 downloads 缓存；安装器仍会重新核验。

进程管理仍依赖本机准备好的 Supervisor 和部署环境文件。更换版本、架构或目录后，重新跑版本、协议、模型、权限和恢复验收。

## 代理与飞书接入更新

在用户授权后，从本机当前运行的 Clash Verge / Mihomo 配置导出了节点快照。服务器保留当前选定节点为首选，使用独立 AGENT-PROXY 组；飞书和 DeepSeek 域名直连，其余经该代理组。不包含桌面 Unix controller，也未迁入订阅 URL。节点快照不会自动随订阅刷新，后续需重新导出或单独配置刷新机制。

- 显式经 `http://127.0.0.1:7890` 请求 Google 首页得到 HTTP 200，约 1.14 秒；同机直连对照超时。该结果证明此代理链路可访问 Google，不代替 Codex 账号登录验收。
- 正式 Mihomo 配置在服务器私密目录；代理和控制器分别只监听 `127.0.0.1:7890` / `127.0.0.1:9090`，控制器使用独立随机密钥，TUN 关闭。
- 用户提供的飞书应用凭证和本人 open_id 已注入私密 api.env；应用认证、机器人信息查询成功。
- API bridge 已运行并成功建立飞书 WebSocket 长连接；发送给用户本人的连接确认消息成功。
- 当前 api、codex、mihomo 均为 RUNNING；Codex 后续通过独立扫码创建的应用「Server Codex」接入，ChatGPT 登录与调用已验证。
- 首次联调没有收到手机消息。检查发现控制台的“已添加事件”为空，添加窗口中的 `im.message.receive_v1` 灰色不可选。用户补齐权限/事件并发布，bridge 重连后发送新消息，成功触发模型。长连接在线不代表事件已经订阅。
- 后续消息往返测试中，模型读取 `acceptance-marker.txt` 并回复正确随机标记，服务端记录 turn complete，飞书客户端显示正确回复。
- 停止 API bridge 后重新启动，日志确认从磁盘载入会话，原生会话 ID 保持一致；续聊成功。随后发出“不要调用工具、根据对话历史复述”指令，日志 tools=0，模型正确回复最初标记与暗号，飞书客户端再次确认显示。
- 中文客户端验收指令通过粘贴输入并在发送前核对；原生逐键输入曾丢失中文，只发送了文件名，该轮触发 Read，不计入 tools=0 验收。
- bridge 映射在私密状态目录 `api/sessions/`，Claude 原生会话与本次写入的项目记忆在 `/root/.claude/projects/`；重启只载入映射不足以证明续聊，要同时确认原生记录可用。

两条运行配置和对应模板均已固定 `reasoning_effort = "high"`，重启后真实调用记录一致。私有测试群已完成 Codex 派工 → CC 统计文件 → 同话题单次审批 → CC 回报 → Codex 验收；目前按话题保存上下文，仅允许本人和已核实的对端机器人。换机复用及完整群聊配置见 [机器人换机与群聊共用](robot-reuse-and-groups.md)。其他用户加入与多人共享上下文尚未测试。

## 2026-09-22 消息排版调整

两份私密运行配置已开启 `enable_feishu_card`，并追加 `FEISHU_MESSAGE_FORMAT_V1` 回复约定：普通回复和报告摘要不带机器人提及，长报告按允许的产物范围发送 `.md` 附件，派工或回报用独立的简短提及通知。原有对端别名、单次派工与回报约定、模型和审批模式保留。四份部署模板也已同步；具体交付步骤见 [消息排版与报告交付](robot-reuse-and-groups.md#消息排版与报告交付)。

现场确认两个 agent 的任务已结束后，备份运行配置和 bridge 会话记录，再重启两条 bridge。启动前检查通过，重启后两份 bridge 会话文件与备份逐字节一致。本地 16 项离线检查通过。手机排版、附件下载、修改后的机器人往返及卡片批准/拒绝仍待实测，不能把配置载入等同于端到端通过。

同日进一步将两边默认显示模式设为 `compact`，显式关闭 `thinking_messages` 和 `tool_messages`，并同步四份部署模板。两条运行配置已备份、通过启动前检查并重启载入，会话文件与备份逐字节一致；16 项离线检查通过。多工具任务在手机端不刷屏、审批仍可操作的实际表现按 A17 继续验收。

## 2026-09-22 切换到另一台实例

两个 bot 已切换到新 AutoDL 实例，复用原应用身份、配置、登录态和会话文件。旧机两个 bridge 保持停止，bot 开机入口已备份并暂时停用；新机本次手动启动，尚未安装 bot 开机钩子。过程、验证结果和回滚边界见 [换机记录](server-migration-validation.md)，后续自启动策略另行讨论。
