# 两个应用使用一致的飞书权限

`configs/feishu-agent-scopes.json` 是 2026-09-22 从已创建的 Server Codex 应用实际授权清单提取的配置快照：35 项应用身份权限、1 项用户身份权限。它用于用户明确选择的扩展功能路线，包含消息、附件、卡片、文档、评论、知识库节点及应用自身管理等能力；不是所有简单聊天机器人的最低要求。

## 为已有机器人对齐权限

若希望应用类型与扫码创建的 Server Codex 一致，采用下一节的新建流程。下面的原地升级方案只增加旧应用权限，不改变其创建来源或客户端展示类型。

1. 保留原 App ID、App Secret、用户白名单、cc-connect project name 和状态目录。增加权限不需要新建机器人，也不需要重新登录模型。
2. 在飞书后台进入目标应用的“权限管理 → 批量处理 → 批量导入/导出权限”，导入 [权限 JSON](../configs/feishu-agent-scopes.json)。
3. 核对新增清单。以原来仅有三项基础消息权限的应用为例，应新增 32 项应用身份权限和 1 项用户身份权限，不重复申请原有三项。
4. 通讯录数据范围沿用“与应用的可用范围一致”。权限对齐不等于扩大可用人员或开启外部共享。
5. 提交配置、创建并发布新版本，检查所有目标权限的实际授权状态。
6. 重新查询两个应用的 `GET /open-apis/application/v6/scopes`，按 `(scope_type, scope_name)` 比较集合，分别核对 `grant_status`。数量相等不代表清单相等。

本项目的私密环境文件只在服务器使用；调用权限查询接口时从文件读取 App Secret，先获取 tenant_access_token，令牌只留在进程内。权限 JSON 不含凭证，私密查询响应不提交到仓库。

## 用同一个扫码流程重新创建应用

`cc-connect v1.5.0 feishu new` 的注册请求使用 `PersonalAgent` 类型；这个飞书应用创建方式与后端选择 Claude Code 或 Codex 无关。两种后端均可使用 [扫码创建流程](codex-server-validation.md#新机器人扫码创建流程)。

1. 备份旧环境文件、bridge 会话 JSON 和模型 CLI 的原生会话目录。备份状态时排除 `run/` 中的运行时 socket，不能把 socket 当普通文件复制。
2. 在独立、权限为 600 的临时 TOML 中填写原项目名称、目录和空的飞书凭证。运行 `cc-connect feishu new`，由用户扫码创建并授权。
3. 核验新 App ID 与旧应用及其他现用应用不同；核验返回的 owner open_id 非空、无通配符、不是机器人自身 ID。不同应用的用户 open_id 不可直接复用。
4. 查询新应用与对照应用的实际权限，比较完整集合及授权状态。相同注册入口通常预配同一组能力，但不能只凭入口或权限数量宣称完全一致。
5. 停止旧 bridge，保留模型认证、工作目录和状态目录，只替换飞书 App ID、App Secret 和用户白名单，再启动 bridge。
6. 新 App ID 会产生新的飞书聊天入口及会话键。服务器上的原生模型记录可以保留，但需要明确关联旧会话，并验证历史暗号和读取项目文件。飞书客户端中旧机器人的消息不会自动搬到新聊天。
7. 验证新应用真实收发成功后，再删除旧应用。删除前以旧 App ID 核对对象，不凭重复的应用名称选择；备份服务器文件不等于能够恢复飞书应用或客户端消息。

这套重建流程用于用户主动更换应用身份。仅更换服务器时，继续复用已有应用凭证和会话备份。

### 2026-09-22 实机结果

已按用户选择，用该流程重新创建 Server CC，飞书客户端显示“智能体”。实际权限集合及授权状态与 Server Codex 完全相同：35 项应用身份权限、1 项用户身份权限；两者均配置 WebSocket `card.action.trigger` 回调。

切换前停止 API bridge，并将唯一操作者的旧会话键映射到新应用的私聊 chat_id 和 owner open_id，保持原 bridge session 与 Claude 原生 session 不变。新应用真实消息触发同一原生会话恢复：先凭历史正确复述旧暗号，再仅调用一次 Read 读出新验收文件。项目目录、DeepSeek Flash 配置和模型认证保持原值。

新入口验证成功后，用户确认删除旧应用；后台列表不再显示旧应用，旧凭证认证返回 `10217 / app has been deleted`，新凭证认证成功。服务器保留迁移前的私密配置与会话备份。此次是同一服务器更换飞书应用的验证，不代替整机关机恢复或换机验收。

## 事件及回调

此快照对应的已具备权限的应用身份事件为：

```text
im.message.receive_v1
im.chat.member.bot.added_v1
im.chat.member.bot.deleted_v1
im.message.reaction.created_v1
im.message.reaction.deleted_v1
drive.notice.comment_add_v1
```

事件和回调均使用长连接，卡片回调为 `card.action.trigger`。保存时按平台要求保持目标 bridge 在线；同一 App ID 只保留一个活跃桥接。

扫码生成的 Codex 应用另列出三个用户身份事件：`vc.meeting.participant_meeting_ended_v1`、`vc.note.generated_v1`、`minutes.minute.generated_v1`，但本快照没有开通它们所需的会议/纪要权限。不要为了复制这三个未具备权限的配置项而额外申请超出目标清单的权限。

## 配好权限后还需什么

- `offline_access` 为用户授权后的令牌续期能力。它不代表已获得用户授权或已持有 user_access_token。
- 文档、知识库、通讯录等数据仍受资源授权和数据范围约束。
- 权限和订阅允许平台访问及推送，并不自动给 cc-connect 增加全部业务功能。文档操作需要实际工具/API 接入与验收。
- 飞书权限与 Claude Code / Codex 的服务器执行审批分别配置。权限对齐不改变两种 CLI 的执行模式。
- 发布后验证原会话的文本往返、会话 ID 与聊天暗号；附件、交互卡片等功能启用时分别实测。

依据：[飞书权限说明](https://open.feishu.cn/document/ukTMukTMukTM/uQjN3QjL0YzN04CN2cDN)、[查询授权状态](https://open.feishu.cn/document/application-v6/scope/list)，以及本次应用后台和只读 API 检查。
