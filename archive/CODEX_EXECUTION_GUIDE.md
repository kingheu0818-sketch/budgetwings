# ?? ARCHIVED (v2.0, 2026-04-21)

This document was archived as part of the v1 -> v2 migration.

- **v1 (archived)**: setup guide for scraper-first execution with early Codex workflows
- **v2 (current)**: agent-oriented architecture under `agents/`, `tools/`, `llm/`
- Kept for historical reference only; it should not guide current development

---

# BudgetWings — Codex 执行指南

> 本文档是给你（项目发起人）的操作手册，告诉你怎么从零开始，用 Codex 把 PRD 变成可运行的代码，全程不需要在本地配任何开发环境。

---

## 第一步：GitHub 仓库初始化（10 分钟）

### 1.1 创建仓库

1. 打开 https://github.com/new
2. 填写：
   - Repository name: `budgetwings`
   - Description: `低价出行情报站 — 票价驱动的短期旅游攻略自动生成`
   - 选 **Public**（开源项目）
   - ✅ 勾选 "Add a README file"
   - License 选 **MIT**
   - .gitignore 选 **Python**
3. 点 "Create repository"

### 1.2 上传 PRD

1. 在仓库页面点 "Add file" → "Upload files"
2. 把 `PRD.md` 拖进去
3. Commit message 写：`docs: add product requirements document`
4. 点 "Commit changes"

### 1.3 创建基础目录结构

在仓库页面点 "Add file" → "Create new file"，依次创建以下空文件（GitHub 会自动创建目录）：

```
scraper/sources/.gitkeep
scraper/__init__.py
engine/__init__.py
guides/asia/.gitkeep
guides/domestic/.gitkeep
web/.gitkeep
bot/.gitkeep
data/deals/.gitkeep
.github/workflows/.gitkeep
docs/.gitkeep
```

> 💡 **小技巧**：在文件名输入框里打 `scraper/sources/.gitkeep` 它会自动帮你建好两级目录。

---

## 第二步：开发环境选择（不用本地配环境）

你有三种方式，**都不需要在 Windows 本地装任何东西**：

### 方案 A：Claude Code（推荐，最省事）

Claude Code 可以直接在 GitHub 仓库上工作。

1. 在 claude.ai 中使用 Claude Code
2. 连接你的 GitHub 仓库
3. 直接用下面的提示词让它开发

### 方案 B：GitHub Codespaces（免费额度够用）

1. 在你的仓库页面，点绿色 "Code" 按钮
2. 切到 "Codespaces" 标签
3. 点 "Create codespace on main"
4. 等 1-2 分钟，会打开一个云端 VS Code
5. 在终端里跑代码、装依赖，全部在云端完成
6. GitHub 免费账户每月有 120 小时 Codespaces 额度，够用

### 方案 C：在 Codex 中直接执行

如果你用的是 Anthropic 的 Codex（Claude Code CLI），它本身就可以：
- 克隆你的 GitHub 仓库
- 在沙箱环境中写代码、跑测试
- 直接提交 PR 到你的仓库

---

## 第三步：Codex 提示词（按阶段喂）

> ⚠️ **核心原则**：不要一次性把所有需求丢给 Codex。按模块拆分，每次一个任务，完成后让我（Claude）review，再进入下一个。

---

### 🔵 任务 0：项目骨架搭建

```markdown
## 任务：搭建 BudgetWings 项目骨架

请阅读仓库中的 PRD.md，然后完成以下工作：

### 要求

1. **项目结构**：按照 PRD.md 第 7.2 节的仓库结构创建完整的目录和文件

2. **Python 环境**：
   - 创建 `pyproject.toml`，使用 Python 3.11+
   - 依赖管理用 `uv` 或 `poetry`（优先 uv）
   - 核心依赖：httpx, beautifulsoup4, pydantic, apscheduler, pyyaml
   - 开发依赖：pytest, ruff, mypy

3. **数据模型**（用 Pydantic v2）：
   - `models/deal.py`：定义 Deal 数据模型，字段包括：
     - id (str, uuid)
     - source (str, 数据来源标识)
     - origin_city, origin_code (出发城市和机场代码)
     - dest_city, dest_code (目的地城市和机场代码)
     - price_cny (int, 人民币分)
     - transport_type (enum: flight/train/bus)
     - departure_date, return_date (date)
     - is_round_trip (bool)
     - airline / operator (Optional[str])
     - booking_url (str)
     - scraped_at (datetime, UTC)
     - expires_at (Optional[datetime])
   - `models/guide.py`：定义攻略模板的 Pydantic 模型，对应 PRD 第 5.2 节的 YAML 结构
   - `models/persona.py`：定义 PersonaType enum (WORKER / STUDENT) 和对应的筛选参数

4. **采集器基类**：
   - `scraper/base.py`：定义 `BaseScraper` 抽象类
     - `async def scrape() -> list[Deal]` 抽象方法
     - `name: str` 属性
     - 内置 httpx.AsyncClient，带 timeout (30s)、retry (3次)、rate limiting
     - 友好的 User-Agent: "BudgetWings/0.1 (+https://github.com/你的用户名/budgetwings)"
   - `scraper/registry.py`：采集器注册表，支持动态注册和批量执行

5. **配置管理**：
   - `config.py`：用 pydantic-settings，支持 .env 和环境变量
   - 不硬编码任何 API key

6. **基础文档**：
   - 更新 `README.md`：项目介绍、功能说明、如何运行、如何贡献
   - `docs/CONTRIBUTING.md`：贡献指南
   - `docs/GUIDE_TEMPLATE.md`：攻略模板编写规范（附一个示例）

7. **CI 配置**：
   - `.github/workflows/ci.yml`：PR 时自动跑 ruff lint + mypy + pytest

### 约束
- 所有 Python 文件必须有 type hints
- 不写任何实际的爬虫逻辑，只搭骨架和接口
- 代码风格遵循 ruff 默认配置
- 每个模块有 `__init__.py` 做清晰的导出
```

---

### 🔵 任务 1：第一个数据源采集器（Kiwi.com）

```markdown
## 任务：实现 Kiwi.com 采集器

基于已有的 BaseScraper 基类，实现第一个实际的数据源采集器。

### 背景
Kiwi.com 提供 Tequila API（https://tequila.kiwi.com/），有免费 tier，
适合作为 MVP 的第一个数据源。

### 要求

1. **采集器实现** `scraper/sources/kiwi.py`：
   - 继承 BaseScraper
   - 使用 Kiwi Tequila Search API
   - 输入：出发城市列表、搜索日期范围、价格上限
   - 输出：标准化的 Deal 列表
   - API Key 从环境变量 `KIWI_API_KEY` 读取

2. **搜索策略**：
   - 默认搜索从以下城市出发的航班：
     北京(BJS)、上海(SHA)、广州(CAN)、深圳(SZX)、成都(CTU)、杭州(HGH)
   - 搜索未来 7-60 天的航班
   - 单程价格低于 ¥1500 的才入库
   - 支持 "anywhere" 目的地搜索（发现最便宜的目的地）

3. **数据标准化**：
   - 把 Kiwi 返回的数据转换为 Deal 模型
   - 价格转换为 CNY 分（如果返回的是其他货币，用当日汇率转换）
   - booking_url 使用 Kiwi 的 deeplink

4. **错误处理**：
   - API 限流时自动等待重试
   - 网络超时的指数退避重试
   - 记录详细日志（用 structlog 或标准 logging）

5. **测试**：
   - `tests/test_kiwi_scraper.py`
   - 用 mock 数据测试数据转换逻辑
   - 不需要在测试中实际调 API

6. **使用文档**：
   - 在 `docs/DATA_SOURCES.md` 中记录 Kiwi 数据源的接入方式、
     API 申请步骤、环境变量配置

### 约束
- 遵守 Kiwi API 的 rate limit
- 不要硬编码 API key
- 采集频率：每次采集间隔至少 1 秒
```

---

### 🔵 任务 2：Deal 排名引擎 + 人群策略

```markdown
## 任务：实现 Deal 排名引擎和人群策略过滤器

### 要求

1. **Deal 排名器** `engine/deal_ranker.py`：
   - 输入：Deal 列表 + PersonaType
   - 输出：排序后的 Deal 列表（带评分）
   - 评分因子：
     - 价格得分（越便宜越高，相对于该航线历史均价）
     - 时间便利性得分（周五晚/周六早出发加分）
     - 目的地热度得分（热门目的地适当加分）
     - 签证友好度（免签/落地签加分）
   - 打工人模式和学生党模式的权重不同（参考 PRD 第 4.1 节）

2. **人群策略过滤器** `engine/persona_filter.py`：
   - 实现 PRD 第 4.1 节定义的所有筛选逻辑差异
   - WorkerFilter：
     - 只保留未来 2-4 个周末 + 下一个小长假的 deal
     - 默认排除红眼航班（22:00-06:00 出发）
     - 只保留直飞或短中转（< 3h）
     - 价格上限 ¥1500 单程
   - StudentFilter：
     - 保留未来 30-90 天所有日期
     - 包含红眼航班
     - 接受长中转
     - 价格上限 ¥500 单程
     - 优先火车硬座/硬卧 > 廉航 > 大巴

3. **拼假日历** `engine/holiday_calendar.py`：
   - 内置中国法定节假日数据（2026-2027）
   - 计算"请 N 天假 = 玩 M 天"的拼假方案
   - 输出推荐的出行日期区间

4. **测试**：
   - 为排名器和过滤器写完整的单元测试
   - 覆盖边界情况：空列表、全部被过滤、价格为 0 等

### 约束
- 排名算法的权重要可配置（写在 config 里），不要硬编码
- 所有日期计算要考虑时区（用户在东八区）
```

---

### 🔵 任务 3：攻略生成引擎

```markdown
## 任务：实现攻略生成引擎

### 要求

1. **攻略模板**：
   - 在 `guides/` 目录下创建至少 10 个目的地的 YAML 模板
   - 遵循 PRD 第 5.2 节定义的模板结构
   - 必须包含：清迈、曼谷、大阪、东京、首尔、济州岛、
     新加坡、吉隆坡、成都、三亚
   - 每个模板要有 2day 和 3day 两种行程版本
   - 数据不需要 100% 准确，但要合理（后续社区会修正）

2. **攻略生成器** `engine/guide_generator.py`：
   - 输入：一个 Deal + PersonaType
   - 输出：结构化的攻略内容（GuideOutput 模型）
   - 逻辑：
     a. 根据 Deal 的目的地匹配 YAML 模板
     b. 根据旅行天数选择对应的行程模板
     c. 根据 PersonaType 选择对应的住宿/餐饮/交通推荐
        （参考 PRD 第 4.2 节的内容差异表）
     d. 注入动态数据：实际票价、出行日期
     e. 计算总预算估算

3. **攻略输出模型** `models/guide_output.py`：
   - destination_name
   - persona_type
   - deal_summary (票价信息摘要)
   - visa_info
   - weather_note
   - daily_itinerary: list[DayPlan]
   - accommodation_suggestions
   - food_suggestions
   - transport_tips
   - budget_breakdown (各项花费明细)
   - total_estimated_budget (不含机票)
   - tips: list[str] (注意事项)

4. **Markdown 渲染器** `engine/guide_renderer.py`：
   - 把 GuideOutput 渲染成漂亮的 Markdown
   - 打工人版和学生党版用不同的标题和措辞风格
   - 打工人版标题风格："🧳 周末速游清迈 | 往返 ¥680"
   - 学生党版标题风格："💰 清迈穷游 3 天 ¥500 搞定"

5. **测试**：
   - 模板加载和匹配的测试
   - 生成逻辑的测试
   - 渲染输出格式的测试

### 约束
- 如果某目的地没有模板，生成器应该返回一个"基础版攻略"
  而不是报错（只包含票价信息和签证/天气）
- YAML 模板必须通过 Pydantic 模型校验
```

---

### 🔵 任务 4：每日 Deal Feed 页面（前端）

```markdown
## 任务：实现 BudgetWings 前端页面

### 要求

1. **技术栈**：
   - Next.js 14+ (App Router)
   - TypeScript strict mode
   - TailwindCSS
   - 静态生成 (SSG) — 用 generateStaticParams
   - 部署到 Vercel

2. **页面**：

   a. **首页** `/`
   - 顶部：模式切换（打工人 🧳 / 学生党 🎒），用 toggle 按钮
   - 打工人模式首页标题："这个周末去哪浪？"
   - 学生党模式首页标题："最便宜能去哪？"
   - Deal 卡片列表：
     - 航线（出发 → 目的地）
     - 价格（大字加粗）
     - 出行日期
     - 交通方式 icon
     - "查看攻略" 按钮
     - "去订票" 外链按钮
   - 筛选栏：出发城市、价格区间、日期范围、交通方式
   - 排序：打工人默认按日期，学生党默认按价格

   b. **攻略详情页** `/guide/[deal-id]`
   - 展示完整攻略内容
   - 顶部 hero：目的地名 + 票价 + "去订票" 按钮
   - 攻略正文（从 Markdown 渲染）
   - 预算明细表格
   - 底部：相关 deal 推荐

   c. **关于页** `/about`
   - 项目介绍、开源信息、贡献方式

3. **数据**：
   - MVP 阶段直接读取 `data/deals/` 目录下的 JSON 文件
   - 构建时生成静态页面
   - 不需要后端 API

4. **设计要求**：
   - 移动端优先（大部分用户手机刷）
   - 暗色模式支持
   - 加载速度要快（Lighthouse Performance > 90）
   - 卡片要有视觉吸引力：价格用大号醒目字体，
     低于历史均价的标 "🔥 历史低价"

5. **SEO**：
   - 每个攻略页有独立的 meta title 和 description
   - 结构化数据 (JSON-LD)
   - sitemap.xml 自动生成

### 约束
- 不使用任何付费字体
- 图片用 emoji 或免费 icon 替代（MVP 不做图片）
- 所有文案支持中文
```

---

### 🔵 任务 5：定时任务 + Telegram Bot + 部署

```markdown
## 任务：自动化流水线 + Telegram Bot + 部署

### 要求

1. **GitHub Actions 定时采集** `.github/workflows/scrape.yml`：
   - 每天 UTC 00:00 和 12:00 自动执行（对应北京时间 8:00 和 20:00）
   - 步骤：
     a. checkout 仓库
     b. 安装 Python 依赖
     c. 运行采集脚本（所有已注册的数据源）
     d. 运行排名引擎，生成当日 deal 榜单
     e. 运行攻略生成器，为 TOP 20 deal 生成攻略
     f. 把结果写入 `data/deals/YYYY-MM-DD.json` 和 `data/guides/`
     g. 自动 commit 并 push 到 main
     h. 触发 Vercel 重新部署（通过 deploy hook）
   - 失败时发送通知到 Telegram

2. **Telegram Bot** `bot/`：
   - 框架：python-telegram-bot
   - 命令：
     - `/start` — 欢迎信息 + 模式选择
     - `/deals` — 今日低价 TOP 10
     - `/deals 清迈` — 搜索特定目的地
     - `/mode worker` / `/mode student` — 切换模式
     - `/subscribe` — 订阅每日推送
     - `/budget 2000` — 预算倒推（输入总预算，返回推荐）
   - 每日定时推送（早 8 点）：给订阅用户发送当日精选 deal
   - 消息格式：卡片式，含价格、日期、一键跳转链接

3. **部署配置**：
   - `vercel.json`：前端部署配置
   - 环境变量文档：列出所有需要配置的 env vars 和获取方式
   - `.env.example`：示例环境变量文件

4. **监控**：
   - 采集失败 → Telegram 告警
   - 数据量异常（今日 deal 数量为 0）→ 告警
   - 简单的 health check endpoint

### 约束
- Bot token 从环境变量读取，不提交到代码
- GitHub Actions 的 secrets 配置写进文档
- 自动 commit 使用 bot 账户，commit message 格式：
  `data: update deals for YYYY-MM-DD`
```

---

## 第四步：Review 流程

每个任务 Codex 完成后，把代码给我（Claude）review。我会检查：

| 检查项 | 说明 |
|--------|------|
| 是否符合 PRD | 功能是否完整实现了 PRD 的定义 |
| 代码架构 | 模块分离是否清晰，依赖方向是否正确 |
| 类型安全 | type hints 是否完整，Pydantic 模型是否合理 |
| 错误处理 | 网络请求、数据解析有没有正确处理异常 |
| 测试覆盖 | 核心逻辑有没有测试，边界情况有没有覆盖 |
| 安全 | 有没有硬编码 key，有没有隐私泄露风险 |
| 可维护性 | 新增数据源/目的地的成本是否足够低 |

### Review 提交方式

直接把 Codex 生成的代码文件（或 GitHub PR 链接）发给我，说一句：
> "任务 X 完成了，帮我 review"

我会逐文件给出反馈。

---

## 第五步：上线 Checklist

- [ ] 仓库 README 完善（含截图/GIF）
- [ ] LICENSE 文件存在
- [ ] .env.example 包含所有环境变量
- [ ] GitHub Actions 跑通一次完整采集
- [ ] Vercel 部署成功，页面可访问
- [ ] Telegram Bot 响应正常
- [ ] 至少 10 个目的地有攻略模板
- [ ] 至少 1 个数据源稳定产出 deal
- [ ] CONTRIBUTING.md 清晰可操作
- [ ] 创建 5 个 "good first issue" 引导社区参与

---

## FAQ

### Q: 我不会用命令行怎么办？
A: 用 GitHub Codespaces 或 Claude Code，两者都提供完整的云端开发环境，在浏览器里操作就行。

### Q: Codex 一次写不完一个任务怎么办？
A: 正常。可以让它先完成核心部分，review 后再补充。把一个任务拆成更小的子任务也完全可以。

### Q: 免费额度够用吗？
A: GitHub Actions 免费账户每月 2000 分钟，Codespaces 每月 120 小时，Vercel 免费 tier 无限部署。MVP 阶段完全够用。

### Q: 数据源的 API Key 去哪申请？
A: 每个任务的文档里会写。Kiwi Tequila API 在 https://tequila.kiwi.com/ 注册即可，免费 tier 足够 MVP 使用。
