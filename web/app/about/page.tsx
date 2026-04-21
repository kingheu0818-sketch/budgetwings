import Link from 'next/link';

const highlights = [
  'LangGraph workflow for Scout → Validate → Analyst → Retrieve → Guide → Save',
  'RAG knowledge base backed by LanceDB with local sentence-transformer embeddings',
  'MCP server entry so Claude Desktop and other clients can call the tool layer directly',
  'SQLite persistence, LangFuse tracing, and automated evaluation reports',
];

export default function AboutPage() {
  return (
    <main className="mx-auto grid max-w-6xl gap-10 px-4 py-6 sm:px-6 lg:px-8">
      <Link href="/" className="text-sm font-semibold text-emerald-600 dark:text-emerald-300">
        返回首页
      </Link>

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
        <div className="grid gap-4">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-600 dark:text-emerald-300">
            About BudgetWings
          </p>
          <h1 className="text-4xl font-black leading-tight text-zinc-950 dark:text-white sm:text-5xl">
            一个为低价出行场景打造的 Agent Engineering 项目。
          </h1>
          <p className="max-w-2xl text-base leading-7 text-zinc-600 dark:text-zinc-300">
            旅行只是场景，真正的重点是把多 Agent 编排、工具调用、RAG、可观测性、评估体系和自动部署串成一套可长期演进的系统。
          </p>
        </div>

        <img
          src="https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1400&q=80"
          alt="Aerial travel scene"
          className="h-80 w-full object-cover"
        />
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {highlights.map((item) => (
          <div key={item} className="border border-zinc-200 px-5 py-5 dark:border-zinc-800">
            <p className="text-base leading-7 text-zinc-800 dark:text-zinc-200">{item}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-4 border border-zinc-200 px-5 py-5 dark:border-zinc-800">
        <h2 className="text-2xl font-bold text-zinc-950 dark:text-white">系统流程</h2>
        <ol className="grid gap-3 text-sm leading-7 text-zinc-600 dark:text-zinc-300">
          <li>1. Scout 通过搜索和抓取网页发现潜在 deal。</li>
          <li>2. Validator 丢弃无效记录，同时保留失败原因进入数据库。</li>
          <li>3. Analyst 做去重、排序和历史低价判断。</li>
          <li>4. Retrieve 从知识库抽取目的地背景信息。</li>
          <li>5. Guide 生成 Markdown 攻略，并结合 RAG 约束幻觉。</li>
          <li>6. Daily run、evaluation 和网站部署一起形成完整闭环。</li>
        </ol>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="border border-zinc-200 px-5 py-5 dark:border-zinc-800">
          <h3 className="text-xl font-bold text-zinc-950 dark:text-white">为什么适合求职展示</h3>
          <ul className="mt-4 grid gap-2 text-sm leading-7 text-zinc-600 dark:text-zinc-300">
            <li>- 不只展示“会调用模型”，而是展示“会管理 Agent 质量”。</li>
            <li>- 有评估报告、可观测性、数据库、部署链路，像真实系统而不是 demo。</li>
            <li>- CLI、Bot、MCP、Web 四个入口并存，能讲工程分层和交付能力。</li>
          </ul>
        </div>
        <div className="border border-zinc-200 px-5 py-5 dark:border-zinc-800">
          <h3 className="text-xl font-bold text-zinc-950 dark:text-white">代码与运行入口</h3>
          <ul className="mt-4 grid gap-2 text-sm leading-7 text-zinc-600 dark:text-zinc-300">
            <li>- `python cli.py run --city 深圳 --persona worker --top 5 --engine graph`</li>
            <li>- `python cli.py eval --city 深圳 --save`</li>
            <li>- `python -m mcp_server.server`</li>
            <li>- `python -m bot.main`</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
