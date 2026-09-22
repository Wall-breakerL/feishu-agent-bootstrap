# 本地验证记录

初次检查于 2026-09-21 在 macOS 上完成，使用 Python 3.14.7 和 Bash。以下记录覆盖本地脚本与配置，不包含当时尚未进行的服务器联调。

| 检查 | 结果 | 范围 |
|---|---|---|
| `python3 -m unittest discover -s tests -v` | 16 个测试全部通过 | 使用临时目录、假凭证、假 CLI；无网络 |
| `bash -n scripts/run-bridge.sh` | 通过 | Bash 语法 |
| 四个 TOML 模板解析 | 通过 | Python tomllib 语法解析 |
| Markdown 相对文件链接 | 无缺失目标 | 本地文档导航 |
| npm registry `cc-connect/1.5.0` | 包存在，版本为 1.5.0 | 元数据查询，未安装 |
| cc-connect 源码 | 固定 tag / commit 已读取 | 见 research.md |
| 本地 Codex CLI help | 0.145.0 的设备码、API key、stdio app-server 选项存在 | 未调用模型、未改变登录 |

这一阶段没有连接 AutoDL，也没有创建飞书应用、调用模型或发送消息。权限审批、服务器重启和迁移，需要后续在真实环境中分别验证。

其中新增的 6 项离线检查，覆盖运行配置生成与权限、源模板保留、模型选择持久化、已有配置的只读预检，以及 provider 凭证、项目名和 API 认证约束。测试用假 CLI 模拟启动；真实 `/model` 切换和原生会话恢复另行验收。

## 2026-09-22 仓库发布检查

- 16 项离线测试重新通过；所有 Shell 脚本与环境示例通过 `bash -n`，四个 TOML 与权限 JSON 解析通过。
- 新增双机器人环境、部署环境与 Supervisor 示例。使用临时环境中的 Supervisor 4.2.5、setuptools 80.9.0 实际解析服务配置，确认三个 program 正确且均不自动启动；此检查未运行服务。
- 暂存文件通过私密路径、常见密钥与真实应用/用户/群标识检查；所有本地 Markdown 文件链接目标存在。真实私密回执和会话未纳入 Git。
- GitHub Actions 对每次 push / PR 执行离线测试及 Shell、TOML、JSON 语法检查；它不代替飞书和模型实机验收。

后续真实部署、群内协作及重启修复的结果与待测项，见 [服务器操作记录](server-operations.md)。
