# Codex 账号路线实机记录

日期：2026-09-22。使用既有固定版本 Codex 0.155.1、cc-connect 1.5.0 与同一 AutoDL 容器。新增飞书应用和独立项目，原 Claude / DeepSeek 服务继续运行。

## 已验证

- 经服务器 Mihomo 执行 `codex login --device-auth`，用户本人在官方页面完成账号授权；服务器 `codex login status` 返回 `Logged in using ChatGPT`。
- 没有注入 OpenAI API key，没有复制本机 Codex 登录缓存。服务器认证文件为 600。
- 通过 cc-connect 的 `feishu new` 扫码创建独立应用「Server Codex」，自动回填凭证与本应用下的用户 open_id。核验白名单非空、无通配符，且不是机器人自身 ID。
- 新应用认证、机器人信息查询、WebSocket 长连接和向用户本人发送测试说明均成功。
- Codex CLI 在兼容沙箱下真实读取独立项目中的随机验收文件，返回内容与文件一致。
- 手机向新机器人发送读文件指令后，cc-connect 通过 app-server 启动原生会话，真实执行一个工具并返回正确标记；当前实际模型为 `gpt-6-astra`，认证仍为 ChatGPT 账号。
- 停止并启动 Codex bridge 后，磁盘映射重新载入，app-server 恢复同一原生 thread ID；续聊先正确复述只在聊天中给出的暗号，再申请测试文件写入，没有读文件查暗号。
- 飞书显示写入审批后，用户选择“允许所有”，指定测试文件实际产生。随后重启 bridge 清除该临时自动批准状态，重新收到逐次权限请求。
- 独立拒绝测试：在飞书回复“拒绝”，工具取消，agent 停止且目标文件不存在。
- 独立单次允许测试：审批前文件不存在，在飞书只回复“允许”后工具执行成功；服务器核验文件内容逐字节一致。飞书显示完成回复。
- 飞书 `/model` 返回账号可用模型；切至 `gpt-5.6-luna` 后配置写回，再重启 bridge。下一轮原生 turn_context 确认为新模型，原 thread ID 保持；tools=0 正确复述历史暗号、单次允许的文件名与内容，客户端显示同一回复。
- 测试结束从飞书切回 `gpt-6-astra`，保留逐次审批模式。

## AutoDL 沙箱兼容性

默认 Bubblewrap 沙箱启动失败：容器不允许创建所需 namespace。模型能返回回答，但工具没有执行成功，因此首次 CLI 退出码为 0 不能算读文件通过。

本版本支持 `features.use_legacy_landlock = true`，在服务器的 `/root/.codex/config.toml` 设置。只读沙箱下读取文件成功，尝试写入测试项目被 Permission denied 拒绝。

同一组合下 `workspace-write` 测试仍失败，提示需要直接运行时强制执行的权限配置不兼容 legacy Landlock。不能据此宣称 full-auto 可用；不切换 yolo 或关闭沙箱来掩盖失败。该开关在当前 CLI 标记为 deprecated，升级时必须重新验收，不作为任意 Linux 环境的默认配置。

当前可用的是“只读默认 + 逐次批准具体写入命令”：原生 Codex 发起指定命令审批，cc-connect 经飞书转回决策，批准后执行该命令。通过这一测试不代表 `workspace-write` 沙箱已经修复，也不代表未审批命令可以写入。此次未专项验收 Patch 审批、交互卡片按钮、额外目录授权或其他网络权限请求。

本机 `codex sandbox` 的命令写法是 `codex sandbox -- COMMAND`，不是旧文档中的 `codex sandbox linux -- COMMAND`。无模型调用的检查示例：

```bash
codex -c features.use_legacy_landlock=true \
  -c 'sandbox_mode="read-only"' sandbox -- cat acceptance-marker.txt
```

## 当前运行配置

- `BRIDGE_PROFILE=codex-approval`：`app_server` / `stdio://` 后端，`suggest` 模式映射为只读沙箱与 `on-request` 审批。
- 工作目录：`/root/autodl-tmp/feishu-agent-demo/codex`。
- bridge 状态：`/root/.local/state/feishu-agent/codex`；Codex 原生记录：`/root/.codex`。
- 私密配置：`/root/.config/feishu-agent/codex.env`，API 凭证不进入此路线。

飞书往返、指定命令的单次允许与拒绝、bridge 重启续聊、模型切换与选择持久化已通过。后续已完成机器人群内协作、用户重启后的人工恢复，并接入开机钩子；修复后的整机自动恢复、换服务器、长任务和其他用户加入仍待验收。最新边界见 [服务器记录](server-operations.md)，不将 bridge 进程重启当作整机自动启动通过。

## 飞书文本审批

先发送任务，等机器人显示具体权限请求，再回复 **允许** 或 **拒绝**（不加斜杠）。第一次测试只允许一次，不用“允许所有”。

`/allow` 是工具预授权命令，Codex 未实现这项接口，会回复“此代理不支持工具授权”。这与 app-server 的逐次权限审批不同。实测曾在任务尚未投递、没有待审批请求时发送 `/allow`，因此收到该提示；不应以此判断账号登录或 Codex 审批后端失败。

“允许所有”作用于 bridge 当前运行会话的自动审批状态。本次实测重启 bridge 后该状态清除，但原生聊天历史仍恢复。日常首次操作建议核对命令后单次允许。

## 飞书内切换模型

```text
/model
/model switch gpt-5.6-luna
/model switch gpt-6-astra
```

可用项以自己账号的实际列表及成功调用为准。切换后上下文保留，运行 TOML 中的 model 写回；此次通过重启后的真实调用验证了持久化。不要只凭“已切换”的文字确认实际模型。

## 新机器人扫码创建流程

使用临时私密 TOML（600），其中只放目标项目与平台，先不要启动 bridge：

```bash
umask 077
cc-connect feishu new \
  --config /private/path/onboarding.toml \
  --project demo-codex \
  --timeout 900 \
  --qr-image /private/path/onboarding.png \
  --set-allow-from-empty
```

用户用飞书扫描短时二维码并确认新建应用。返回后核验机器人名称、发布状态、订阅和 owner open_id，再将凭证移入独立环境文件；运行 TOML 继续使用环境变量引用。不要启用 `--debug`，也不要把生成的私密 TOML、二维码或含凭证的输出纳入仓库。扫码预配的事件仍需真实收发验证。

依据：[cc-connect 固定版本飞书接入](https://github.com/chenhg5/cc-connect/blob/v1.5.0/docs/feishu.md)、[OpenAI 设备码认证](https://learn.chatgpt.com/docs/auth#login-on-headless-devices)，以及本次服务器命令与私密日志。
