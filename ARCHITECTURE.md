# BudgetWings v2 — AI 旅行智能体架构

> 从"爬虫工具"升级为"AI Agent 项目"
> 框架固定，能力随大模型进化而进化

---

## 1. 为什么要转型

| 旧方案（爬虫） | 问题 |
|---------------|------|
| 依赖 Kiwi/Amadeus API | 企业级准入，个人项目难申请 |
| 每个数据源写一个爬虫 | 维护成本高，网站改版就挂 |
| 数据结构写死 | 无法适应新的出行方式和平台 |
| 攻略是静态模板 | 不够智能，千篇一律 |

**新方案：让 AI Agent 自己去网上找低价信息，自己生成攻略。**

---

## 2. 新架构：Agent 框架

```
用户输入（或定时触发）
       │
       ▼
┌──────────────────────────────────────────────┐
│              Orchestrator（调度器）             │
│  接收任务 → 拆解子任务 → 分发给 Agent → 汇总结果  │
└──────────────┬───────────────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│ Scout  │ │Analyst │ │ Guide  │
│ Agent  │ │ Agent  │ │ Agent  │
│        │ │        │ │        │
│发现低价  │ │分析比较  │ │生成攻略  │
│出行信息  │ │筛选排序  │ │输出方案  │
└────┬───┘ └────┬───┘ └────┬───┘
     │          │          │
     ▼          ▼          ▼
┌──────────────────────────────────────────────┐
│              Tool Layer（工具层）               │
│  Web Search │ Web Fetch │ Price Parser │      │
│  Weather API│ 汇率转换   │ 签证数据库   │ ...  │
└──────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│              Output Layer（输出层）             │
│  JSON 存储 │ Markdown 攻略 │ Telegram 推送     │
│  Web 页面  │ RSS Feed     │ GitHub Pages      │
└──────────────────────────────────────────────┘
```

---

## 3. 三个核心 Agent

### 3.1 Scout Agent（侦察兵）

**职责**：联网搜索，发现低价出行信息

**工作方式**：
- 不依赖任何固定 API
- 用 web search 搜索："北京出发 特价机票 本周"、"上海飞东南亚 廉航促销"
- 搜索各航司官网促销页、OTA 特价专区、旅游论坛薅羊毛帖
- 抓取搜索结果页面，提取价格和链接
- 输出标准化的 Deal 数据

**Prompt 模板**：
```
你是一个低价出行情报搜集专家。
请搜索从 {origin_city} 出发，未来 {days} 天内的低价出行方式。
包括但不限于：特价机票、火车票折扣、廉航促销、大巴特惠。

要求：
1. 搜索至少 3 个不同来源
2. 只保留单程价格低于 {max_price} 元的信息
3. 必须包含：出发地、目的地、价格、日期、交通方式、订票链接
4. 按价格从低到高排序
5. 以 JSON 格式输出，schema 如下：
   {deal_schema}
```

**可搜索的来源（Agent 自行决定）**：
- Google Flights（搜索结果页，不需要 API）
- 各航司官网促销页面
- 去哪儿/飞猪/携程 特价专区
- 马蜂窝/穷游 特价帖
- Telegram 特价机票频道
- 小红书/微博 低价机票博主

### 3.2 Analyst Agent（分析师）

**职责**：对 Scout 找到的数据做分析、排序、去重、人群适配

**工作方式**：
- 接收 Scout 的原始 Deal 列表
- 去重（同一航线同一日期同一价格）
- 根据 PersonaType 过滤和排序
- 标注"是否历史低价"（与过往数据对比）
- 标注签证友好度、天气适宜度
- 输出排名后的 Deal 列表

**Prompt 模板**：
```
你是一个旅行数据分析师。
以下是今日搜集到的低价出行信息：
{raw_deals}

用户画像：{persona_type}（打工人/学生党）
用户出发城市：{origin_city}

请完成以下分析：
1. 去除重复信息
2. 根据用户画像筛选（打工人看周末可行性，学生党看绝对低价）
3. 按综合性价比排序，给出 TOP 10
4. 为每个 deal 标注：签证类型（免签/落地签/需办理）、当前天气
5. 以 JSON 格式输出
```

### 3.3 Guide Agent（攻略师）

**职责**：根据具体的 Deal，生成个性化短期旅游攻略

**工作方式**：
- 接收一个 Deal + PersonaType
- 联网搜索目的地的最新旅游信息
- 生成完整的短期攻略
- 根据人群类型调整内容风格和推荐

**Prompt 模板**：
```
你是一个专业旅行攻略师。
请为以下出行方案生成一份 {days} 天短期旅游攻略：

出行信息：
- 出发地：{origin}
- 目的地：{destination}
- 交通方式：{transport}
- 出发日期：{departure_date}
- 返回日期：{return_date}
- 票价：{price}

用户类型：{persona_type}

{persona_instructions}

请搜索该目的地最新的旅游信息，然后生成攻略，包含：
1. 签证提示
2. 当地天气与穿衣建议
3. 每日行程安排（具体到上午/下午/晚上）
4. 住宿推荐（含价格区间）
5. 餐饮推荐（含人均价格）
6. 当地交通方式
7. 总预算估算（不含大交通）
8. 注意事项和省钱技巧

以 Markdown 格式输出。
```

**人群指令差异**：
```python
PERSONA_INSTRUCTIONS = {
    "worker": """
目标用户是打工人，特点：
- 时间紧凑，行程要高效
- 预算相对宽裕，人均住宿 ¥200-500/晚
- 推荐性价比高的餐厅，人均 ¥50-150
- 交通可以打车，节省时间
- 标题风格："🧳 周末速游{destination} | 往返 ¥{price}"
""",
    "student": """
目标用户是学生党，特点：
- 时间灵活，可以慢节奏
- 预算极低，住宿 ¥30-100/晚（青旅/胶囊为主）
- 以街边摊、夜市、便利店为主，人均 < ¥30
- 交通以公交/步行/共享单车为主
- 列出所有免费景点，标注学生票折扣
- 标题风格："💰 {destination}穷游 {days} 天 ¥{budget} 搞定"
"""
}
```

---

## 4. 工具层（Tools）

Agent 不直接调 API，而是通过标准化的 Tool 接口操作。
不同的大模型（Claude/GPT/Gemini/开源模型）都可以调用这些 Tool。

### 4.1 核心 Tools

| Tool 名称 | 功能 | 实现方式 |
|-----------|------|---------|
| `web_search` | 联网搜索 | 大模型自带 / SerpAPI / Tavily |
| `web_fetch` | 抓取网页内容 | httpx + BeautifulSoup |
| `price_parser` | 从网页文本中提取价格信息 | LLM 结构化输出 |
| `weather_lookup` | 查询目的地天气 | Open-Meteo API（免费） |
| `currency_convert` | 汇率转换 | exchangerate-api（免费） |
| `visa_lookup` | 查询签证政策 | 本地 JSON 数据库 + 定期更新 |
| `holiday_calendar` | 中国节假日和拼假方案 | 本地数据 |
| `deal_storage` | 存储和读取 Deal 数据 | SQLite / JSON 文件 |
| `guide_renderer` | 渲染攻略为 Markdown/HTML | Jinja2 模板 |

### 4.2 Tool 接口标准

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class ToolInput(BaseModel):
    """每个 Tool 的输入都是一个 Pydantic 模型"""
    pass

class ToolOutput(BaseModel):
    """每个 Tool 的输出都是一个 Pydantic 模型"""
    success: bool
    data: dict | list | str | None = None
    error: str | None = None

class BaseTool(ABC):
    name: str
    description: str  # 给 LLM 看的工具描述

    @abstractmethod
    async def execute(self, input: ToolInput) -> ToolOutput:
        """执行工具"""

    def to_schema(self) -> dict:
        """导出为 LLM function calling 的 schema 格式"""
        ...
```

---

## 5. 大模型适配层（LLM Adapter）

**关键设计：框架不绑定任何一个大模型。**

```python
from abc import ABC, abstractmethod

class LLMAdapter(ABC):
    """大模型适配器基类"""

    @abstractmethod
    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        """发送消息，获取回复"""

    @abstractmethod
    async def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        """发送消息并支持 function calling / tool use"""

class ClaudeAdapter(LLMAdapter):
    """Anthropic Claude 适配器"""
    ...

class OpenAIAdapter(LLMAdapter):
    """OpenAI GPT 适配器"""
    ...

class OllamaAdapter(LLMAdapter):
    """本地开源模型适配器（通过 Ollama）"""
    ...
```

**用户在 config 里选择用哪个模型**：
```env
BUDGETWINGS_LLM_PROVIDER=claude        # claude / openai / ollama
BUDGETWINGS_LLM_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-xxx
```

**不同模型的效果差异是预期内的**：
- Claude/GPT-4：搜索能力强，攻略质量高
- GPT-4o-mini：速度快但深度一般
- 本地开源模型：免费但需要自己加 search 工具

---

## 6. 运行模式

### 6.1 定时模式（每日自动更新）

```
GitHub Actions / cron 定时触发
       │
       ▼
Orchestrator 启动每日任务
       │
       ├─ Scout Agent 搜索 6 个城市的低价信息
       ├─ Analyst Agent 分析排序，输出 TOP 20
       ├─ Guide Agent 为 TOP 10 生成攻略
       ├─ 结果写入 data/ 目录
       ├─ 触发网站重新构建
       └─ Telegram 推送给订阅用户
```

### 6.2 交互模式（用户主动查询）

```
用户通过 Telegram Bot / Web 输入：
"我在深圳，预算 2000，下周末能去哪？"
       │
       ▼
Orchestrator 解析意图
       │
       ├─ Scout Agent 搜索深圳出发的低价信息
       ├─ Analyst Agent 按 ¥2000 预算筛选
       └─ Guide Agent 生成 TOP 3 攻略
              │
              ▼
         返回给用户
```

---

## 7. 新的仓库结构

```
budgetwings/
├── README.md
├── PRD.md
├── ARCHITECTURE.md          # 本文档
├── LICENSE
├── pyproject.toml
├── config.py
│
├── agents/                  # AI Agent 模块
│   ├── __init__.py
│   ├── base.py              # BaseAgent 基类
│   ├── orchestrator.py      # 调度器
│   ├── scout.py             # 侦察兵 Agent
│   ├── analyst.py           # 分析师 Agent
│   └── guide.py             # 攻略师 Agent
│
├── llm/                     # 大模型适配层
│   ├── __init__.py
│   ├── base.py              # LLMAdapter 基类
│   ├── claude.py            # Claude 适配器
│   ├── openai_adapter.py    # OpenAI 适配器
│   └── ollama.py            # Ollama 本地模型适配器
│
├── tools/                   # 工具层
│   ├── __init__.py
│   ├── base.py              # BaseTool 基类
│   ├── web_search.py        # 联网搜索
│   ├── web_fetch.py         # 网页抓取
│   ├── price_parser.py      # 价格提取
│   ├── weather.py           # 天气查询
│   ├── currency.py          # 汇率转换
│   ├── visa.py              # 签证查询
│   └── holiday.py           # 节假日数据
│
├── models/                  # 数据模型（保留现有的）
│   ├── deal.py
│   ├── guide.py
│   └── persona.py
│
├── prompts/                 # Prompt 模板
│   ├── scout.md
│   ├── analyst.md
│   └── guide.md
│
├── data/                    # 输出数据
│   ├── deals/
│   └── guides/
│
├── web/                     # 前端
├── bot/                     # Telegram Bot
│
├── tests/
│   ├── test_agents/
│   ├── test_tools/
│   └── test_models/
│
└── .github/
    └── workflows/
        ├── ci.yml
        └── daily_run.yml
```

---

## 8. MVP 重新定义

### Phase 1（第 1-2 周）：Agent 框架搭建
- [ ] LLM 适配器（先支持 Claude 或 OpenAI 一个）
- [ ] Tool 基类 + web_search + web_fetch 实现
- [ ] Scout Agent 能跑通一次搜索，输出标准 Deal
- [ ] 命令行能运行：`python -m agents.orchestrator --city 深圳`

### Phase 2（第 3-4 周）：功能完善
- [ ] Analyst Agent + 人群策略
- [ ] Guide Agent + 攻略生成
- [ ] 更多 Tools（天气、签证、汇率）
- [ ] 结果写入 JSON + Markdown

### Phase 3（第 5-6 周）：用户触达
- [ ] Telegram Bot 交互模式
- [ ] GitHub Actions 定时运行
- [ ] 静态网站展示每日结果
- [ ] 第二个 LLM 适配器

---

## 9. 成本估算

| 模型 | 每日运行成本（估算） | 说明 |
|------|-------------------|------|
| Claude Sonnet | ~$0.5-1/天 | 6 个城市 × 搜索 + 分析 + 10 篇攻略 |
| GPT-4o-mini | ~$0.1-0.3/天 | 更便宜但质量略低 |
| Ollama 本地 | $0 | 需要有 GPU，搜索能力需自行补充 |

搜索工具成本：
- Tavily API：免费 1000 次/月，够 MVP 用
- SerpAPI：免费 100 次/月
- 大模型自带搜索（Claude/GPT）：包含在模型费用中

---

## 10. 这个项目的独特价值

1. **不依赖任何固定数据源** — API 挂了、网站改版了，Agent 会自己找新的来源
2. **框架固定，能力进化** — 换一个更强的模型，整个系统自动变强
3. **开源社区友好** — 贡献者可以写新的 Tool、新的 Prompt 模板、新的 LLM 适配器
4. **真正的 AI Native 产品** — 不是"传统工具 + AI 外壳"，而是从架构层面就是 Agent 驱动的
