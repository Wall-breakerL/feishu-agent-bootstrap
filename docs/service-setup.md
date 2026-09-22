# 复现双机器人与后台服务

本页把实机使用的独立 Supervisor 方案整理为新实例步骤。目标为 Linux x86_64、Python 3.11+、Bash；开机脚本还需要 `flock` 和 `timeout`。首次部署先完成 [输入清单](deployment-inputs.md) 与 [账号及飞书设置](runbook.md)。已有部署只按差异更新，不覆盖运行配置、登录态或会话。

## 1. 安装固定工具

将仓库放到固定目录，例如 `/root/tools/feishu-agent-bootstrap`，执行：

```bash
cd /root/tools/feishu-agent-bootstrap
python3 scripts/install-linux.py
export PATH="$HOME/.local/opt/feishu-agent/bin:$PATH"
cc-connect --version
codex --version
claude --version
mihomo -v
```

安装器固定下载版本和摘要，安装到独立目录，不启动服务。当前验收组合为 cc-connect 1.5.0、Codex 0.155.1、Claude Code 2.1.278、Mihomo 1.19.31。服务器无法访问下载源时，可在本地下载同一官方资产并传入安装器的 `downloads/` 缓存；仍需通过安装器校验。

检查 `command -v supervisord supervisorctl`。优先复用已有安装；当前实机使用 Supervisor 4.2.5。若不存在，在部署专用 Python 环境安装该版本，并把两个可执行文件的绝对路径填入下一步配置，不替换平台正在运行的管理器。

新建专用环境时可安装 `supervisor==4.2.5 setuptools==80.9.0`；4.2.5 使用 `pkg_resources`，干净的新版 Python venv 不一定提供它。发布前在独立环境用这组依赖解析服务模板，避免仅凭系统中旧环境可用就遗漏依赖。

## 2. 准备私密目录与配置

新部署在确认目录尚未用于其他项目后执行：

```bash
umask 077
mkdir -p "$HOME/.config/feishu-agent/mihomo"
mkdir -p "$HOME/.local/state/feishu-agent/"{logs,api,codex}
cp -n examples/deployment.env.example "$HOME/.config/feishu-agent/deployment.env"
cp -n examples/supervisord.conf.example "$HOME/.config/feishu-agent/supervisord.conf"
cp -n examples/api.env.example "$HOME/.config/feishu-agent/api.env"
cp -n examples/codex.env.example "$HOME/.config/feishu-agent/codex.env"
cp -n examples/proxy.env.example "$HOME/.config/feishu-agent/proxy.env"
```

`cp -n` 避免覆盖旧文件；它不保证旧内容符合新模板。逐个编辑仓库之外的副本：

| 文件 | 填写内容 |
|---|---|
| `deployment.env` | 仓库、工具、状态目录；Python、supervisord、supervisorctl 的真实绝对路径 |
| `api.env` | Claude Code 的 API key、模型、API 机器人凭证及该应用下的本人 open_id |
| `codex.env` | Codex 机器人凭证及该应用下的本人 open_id；不填 OpenAI API key |
| `proxy.env` | 当前模板使用回环代理端口 7890，确认与 Mihomo 一致 |
| `mihomo/config.yaml` | 用户授权的完整代理配置，监听回环地址；检查节点、规则及控制器认证 |

目录保持 700、包含凭证的文件保持 600。创建两个环境文件中指定的项目目录；测试目录可以分别 `git init`，实际项目使用已有 Git 仓库，两个 agent 并发写入时采用独立 worktree。

`supervisord.conf.example` 的路径通过导出的 `DEPLOY_STATE_DIR`、`BOOTSTRAP_ROOT` 展开；`agentctl.sh` 会先 source `deployment.env`。直接运行 supervisorctl 时也必须先载入同一环境，否则模板无法展开。Supervisor 的环境变量插值、`autostart` 与 `autorestart` 行为见 [官方配置说明](https://supervisord.org/configuration.html)。这个实例使用独立 Unix socket，不开放管理 HTTP 端口。

## 3. 先代理，再登录，再启动

```bash
bash scripts/agentctl.sh start mihomo
curl --proxy http://127.0.0.1:7890 --max-time 20 -I https://www.google.com/

# 仅首次登录或认证失效时执行，已有有效账号无需重复授权：
bash scripts/agentctl.sh login codex

bash scripts/agentctl.sh check api
bash scripts/agentctl.sh check codex
bash scripts/agentctl.sh start api
bash scripts/agentctl.sh start codex
bash scripts/agentctl.sh status
```

`check` 不是消息往返验收。两个飞书应用都要发布并订阅消息事件；随后分别在手机发送读取测试文件的请求，核对模型实际输出，再验证 [批准与拒绝](acceptance.md)。本次 AutoDL 的 Codex namespace 限制及仅适用于已验收版本的兼容配置，见 [Codex 沙箱记录](codex-server-validation.md#autodl-沙箱兼容性)。不要把该兼容开关无条件用于其他系统。

首次启动会把模板复制成各自状态目录下的运行 TOML，之后复用该文件。`claude-deepseek` 与 `codex-approval` 模板默认 high。模型名称使用各自账号实际可调用的值；本次实测分别为 deepseek-flash、gpt-6-astra。模板修改不会自动改写现有运行 TOML。

## 4. 接入经过核对的开机入口

仅在确认实例会执行 `/etc/autodl.sh` 后，将以下调用接入该脚本；若已有其他启动内容，保留并合并。不要覆盖整份用户脚本，也不要自行重启服务器。

```bash
/bin/bash /root/tools/feishu-agent-bootstrap/scripts/start-after-boot.sh
```

该脚本显式载入部署环境，使用锁防止重复拉起，并按代理、API、Codex 顺序启动；单项失败有限重试。三个 program 保持 `autostart=false`，由脚本负责顺序启动，Supervisor 负责运行期崩溃重启。首次接入先在空闲时测试服务停止后的恢复，再在获准的真实开机后验收；目前实机只完成前者。日志在 `~/.local/state/feishu-agent/logs/boot-start.log`。

其他平台使用自己的开机机制调用同一脚本；没有核实入口时只交付手动恢复命令。完整故障及实机证据见 [重启记录](server-operations.md#重启与自启的当前状态)。

## 5. 群内协作、换机和保存

- 两个机器人在群里互相派工：按 [群聊协作流程](robot-reuse-and-groups.md) 加入指定群、核实对端 sender ID、设置真实提及和话题会话边界。当前停止规则为提示词约定，没有硬性轮数上限。
- 手机切模型与会话：按 [会话与认证设计](session-and-auth.md)，注意 `/reasoning high`、`/provider switch` 会重置当前会话关联。
- 换机器：复用原飞书应用，停止旧节点，迁移项目和私密会话后启动新节点，按 [迁移流程](migration.md) 验收。
- 此仓库保存方案与模板；实际 env、代理节点、OAuth 缓存、原始日志和会话需在仓库之外单独备份。
