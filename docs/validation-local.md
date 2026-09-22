# 本地验证记录

日期：2026-09-21。环境：macOS，本地 Python 3.14.7，Bash。

| 检查 | 结果 | 范围 |
|---|---|---|
| `python3 -m unittest discover -s tests -v` | 16 个测试全部通过 | 使用临时目录、假凭证、假 CLI；无网络 |
| `bash -n scripts/run-bridge.sh` | 通过 | Bash 语法 |
| 四个 TOML 模板解析 | 通过 | Python tomllib；不是上游程序运行验收 |
| Markdown 相对文件链接 | 无缺失目标 | 本地文档导航 |
| npm registry `cc-connect/1.5.0` | 包存在，版本为 1.5.0 | 元数据查询，未安装 |
| cc-connect 源码 | 固定 tag / commit 已读取 | 见 research.md |
| 本地 Codex CLI help | 0.145.0 的设备码、API key、stdio app-server 选项存在 | 未调用模型、未改变登录 |

没有执行：AutoDL 登录、飞书应用创建/发布、API key 使用、真实桥接启动、消息发送、权限审批往返、服务器重启或迁移。实际部署回执必须另写，不能把本记录当作端到端通过证据。

新增 6 项离线检查覆盖运行配置生成与权限、源模板不变、模型选择重启后保留、已有配置只读预检、新增 provider 的缺密钥拒绝、项目名冲突与 API 认证约束。这里用假 CLI 模拟启动，并未执行真实 `/model` 或恢复原生 agent 会话。

## 2026-09-22 仓库发布检查

- 16 项离线测试重新通过；所有 Shell 脚本与环境示例通过 `bash -n`，四个 TOML 与权限 JSON 解析通过。
- 新增双机器人环境、部署环境与 Supervisor 示例。使用临时环境中的 Supervisor 4.2.5、setuptools 80.9.0 实际解析服务配置，确认三个 program 正确且均不自动启动；此检查未运行服务。
- 暂存文件通过私密路径、常见密钥与真实应用/用户/群标识检查；所有本地 Markdown 文件链接目标存在。真实私密回执和会话未纳入 Git。
- GitHub Actions 对每次 push / PR 执行离线测试及 Shell、TOML、JSON 语法检查；它不代替飞书和模型实机验收。

本文开头是初期本地检查记录。后续真实部署、群内协作及重启修复的证据与未完成项统一见 [服务器操作记录](server-operations.md)。
