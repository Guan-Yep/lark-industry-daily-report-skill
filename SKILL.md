---
name: organize-industry-daily-report
description: 当用户需要收集特定行业的日报并整理收藏到知识库时使用此技能。该技能基于飞书CLI，自动从指定信源抓取新闻，按用户提供的行业关键词过滤，使用 LLM 总结核心信息并绘制飞书白板，最后将白板和 Markdown 内容保存到飞书知识库的指定空间和节点下。同时会向用户发送交互式消息卡片以收集喜好反馈，并可通过后台脚本监听反馈。
---

# organize-industry-daily-report 行业日报整理技能

**CRITICAL — 开始前 MUST 先阅读 `../lark-shared/SKILL.md` 了解飞书 CLI 的认证与权限处理。**

## 技能概述

当用户提出“需要XXX行业日报，整理后收藏到知识库”等需求时，触发此技能。
本技能实现了完全自包含的工作流，无需依赖额外的服务端（如 AutoContents 的本地后端）：
1. **配置确认**：询问并确认知识库 Space ID 和父节点 Token。如果用户没有提供，则默认调用飞书 CLI 为用户新建一个知识库空间及根节点。如果用户需要定时执行，记录其定时配置需求。
2. **资讯抓取与过滤**：执行内置的 Python 脚本抓取 RSS 信源，动态加载偏好设置文档中的白名单、黑名单及信源，并按行业关键词过滤。
3. **内容提炼与白板生成**：调用大模型提炼核心信息，并使用 `lark-whiteboard` 生成瀑布流白板 DSL。
4. **知识库文档生成**：使用 `lark-wiki` 和 `lark-doc` 将白板和 Markdown 正文保存到用户指定的知识库空间和节点下。
5. **交互式卡片推送**：生成小红书风格的飞书消息卡片并推送到用户飞书，提供“多推此类”、“减少相似”按钮以收集反馈。
6. **偏好自动学习(RLHF)**：通过内置监听脚本 `scripts/listen_feedback.py` 捕获卡片点击事件，并将新闻关键词动态追加至配置文档。

## 用户配置指南

为了使技能更灵活，支持用户自定义以下参数，**Agent 在执行前应根据上下文提取或向用户询问确认**：

### 前置准备：飞书开发者后台配置 (首次使用必读)

为了让卡片上的“多推此类”、“减少相似”等按钮能够正常响应并自动更新偏好设置文档，你需要确保飞书应用已正确配置了**长连接事件订阅**。否则，点击卡片按钮时客户端会报错 `出错了，请稍后重试 code:200340`。

请按以下步骤配置（仅需一次）：
1. 访问并登录 [飞书开发者后台](https://open.feishu.cn/app/)。
2. 进入你的自建应用详情页。
3. 在左侧菜单找到 **添加功能 -> 机器人 (Bot)**，确保机器人能力已启用。
4. 在左侧菜单找到 **事件与回调 (Event Subscriptions)**：
   - 将“订阅方式 (Subscription method)”配置为 **长连接 (WebSocket)** 并保存。
   - 在下方的“添加事件”中，搜索并勾选 `card.action.trigger`（**接收消息卡片交互事件**）。
5. 进入左侧的 **版本管理与发布**，创建一个新版本并申请发布（企业自建应用通常会自动通过审核）。发布生效后，客户端点击卡片将不再报错。

### 变量参数配置

系统会自动在同级目录（`PARENT_NODE_TOKEN` 下）创建和维护两个核心云文件：
1. **配置表格 (Config Sheet)**：管理具体的信源列表和黑白名单。
2. **长效记忆文档 (Agent Rules)**：记录 Agent 归纳出的选择规律和偏好总结。

*(在首次运行或更换 `SPACE_ID` / `PARENT_NODE_TOKEN` 时，Agent 会自动销毁旧配置并在新位置重新创建这两个云文件)*

2. **飞书知识库配置**：
   - `SPACE_ID`（默认值：`7631384852998147284`）：保存日报的知识库空间 ID。
   - `PARENT_NODE_TOKEN`（默认值：`ZDmjwQGYdiplgakjQi5c6d5GnBh`）：空间下指定节点的 Token。
   *(用户可随时在对话中提供新的 ID 和 Token，Agent 执行时将动态替换变量。)*

3. **定时任务设置**：
   用户可以要求将此技能设为“定时任务”（例如：每天早上9点执行）。
   - Agent 应向用户提供设置定时任务的操作指南，如在 Windows 中创建任务计划程序，或在 Linux/macOS 中使用 `crontab` 定时调用 Trae Agent 触发此指令。

## 工作流 (Workflow)

### Step -1: 自动工作区检测 (Workspace Setup)

Agent 启动后，必须先检查工作区配置。运行：
```bash
python scripts/setup_workspace.py <SPACE_ID> <PARENT_NODE_TOKEN>
```
此脚本会自动判断目录是否更换。如果是首次运行或更换了目录，脚本将自动在指定的 `PARENT_NODE_TOKEN` 目录下创建两个云端配置：
1. **Agent 偏好与信源配置表 (Sheet)**
2. **Agent 选择规律记忆文档 (Docx)**

并将它们的 Token 保存在本地的 `local_state.json` 中供后续步骤调用。

### Step 0: 学习偏好与规律更新 (Agent as Learner)

在开始生成日报之前，或者当用户明确提出“学习偏好”要求时，运行 `scripts/agent_learner.py` 脚本：
```bash
python scripts/agent_learner.py
```
该脚本会：
- 读取工作区内的 `feedback_history.json`（由后台监听脚本自动写入）。
- 结合大模型/分析逻辑，将用户的兴趣偏好归纳并写入 `references/agent-rules.md` 作为长效记忆（Long-term Memory）。
- 清空当前已学习的反馈历史。
- 在之后的资讯过滤和归类时，Agent 将结合这个 rules 文件进行语义筛选。

### Step 1: 抓取与过滤行业资讯

使用技能内置的 Python 脚本 `scripts/fetch_news.py` 抓取 RSS 信源。脚本会从 `local_state.json` 自动读取 `config_sheet_token`。

```bash
# 运行脚本，传入用户指定的行业关键词
python scripts/fetch_news.py "<行业关键词>" > all_news.json
```
*注：脚本会输出 JSON 格式的资讯列表。如果输出为空，说明当日无相关资讯，请告知用户并结束任务。*

### Step 2: 提炼核心内容与生成白板

基于 `all_news.json`，Agent 需自行对内容进行分析和提炼（参考 `references/prompts.md` 中的系统提示词风格）：
1. **分类与提炼**：将新闻严格归类为：客观事实类速报、话题引导推文、工具/产品推荐。将结果严格按照下面示例结构保存到 `categorized_news.json`（必须使用 UTF-8 编码）。
   ```json
   {
     "date": "2026-04-23",
     "intro": "一段总导语总结今日核心动态...",
     "categories": [
       {
         "name": "客观事实类速报",
         "items": [
           {"title": "xxx", "desc": "xxx", "link": "https://..."}
         ]
       }
     ]
   }
   ```
2. **生成报告文件**：运行内置的 Python 脚本，动态生成 Markdown 正文和适配瀑布流排版的画板 DSL。
   ```bash
   python scripts/generate_report.py
   ```
   *注：此脚本会根据 `categorized_news.json` 输出 `summary.md` 和 `board.json`。*

### Step 3: 创建飞书知识库文档并写入

**1. 创建新文档**
文档标题格式应为：`<当前日期> <行业关键词>行业日报`。
```bash
lark-cli wiki +node-create --space-id <SPACE_ID> --parent-node-token <PARENT_NODE_TOKEN> --title "<当前日期> <行业关键词>行业日报" --obj-type docx --as user
```
*记录返回结果中的 `obj_token`（真实的 docx token）。*

**2. 在文档中创建空白白板 Block**
```bash
# 务必使用 Python 脚本生成干净的 wb.md，避免终端拼接引发的引号转义错误
python -c "with open('wb.md', 'w', encoding='utf-8') as f: f.write('<whiteboard type=\"blank\"></whiteboard>')"
lark-cli docs +update --doc <obj_token> --mode append --markdown "@wb.md" --as user
```
*从响应的 `data.board_tokens[0]` 中提取新建的白板 token。*

**3. 将生成的白板 DSL 写入白板**
```bash
# 使用 whiteboard-cli 编译并输出到文件
npx -y @larksuite/whiteboard-cli@^0.2.0 -i board.json --to openapi --format json -o board_openapi.json

# 更新白板 (使用 @ 文件方式传入 source 避免管道破坏 JSON)
lark-cli whiteboard +update --whiteboard-token <board_token> --source "@board_openapi.json" --input_format raw --idempotent-token <唯一标识，建议10位以上> --overwrite --yes --as user
```

**4. 插入 Markdown 总结正文**
```bash
lark-cli docs +update --doc <obj_token> --mode append --markdown "@summary.md" --as user
```

### Step 4: 生成并推送交互式消息卡片

为了收集用户对新闻的反馈（如“多推此类”、“减少相似”），向用户推送小红书风格的交互式消息卡片。

**1. 生成卡片 JSON**
```bash
# 基于 categorized_news.json 生成 message_card.json
python scripts/generate_message_card.py
```

**2. 发送卡片**
```bash
# 运行发送脚本，将卡片推送到用户飞书中
python scripts/send_card.py
```

### Step 5: 启动/保持后台反馈监听 (可选)

确保启动了用于监听卡片交互事件的后台任务，使得用户在飞书客户端点击卡片时，能够实时更新飞书上的偏好配置文档。
```bash
# 在后台启动事件监听，脚本将捕获 card.action.trigger 并更新文档
python scripts/listen_feedback.py
```
*(注意：需要在飞书开发者后台配置并开通“事件订阅 -> 接收卡片回调”的长连接)*

### Step 6: 通知用户

完成上述步骤后，向用户回复最终的文档链接，并提示用户查看飞书消息卡片进行互动反馈。
