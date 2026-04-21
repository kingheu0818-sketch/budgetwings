import Link from 'next/link';

const highlights = [
  'LangGraph 串起 Scout、Validate、Analyst、Retrieve、Guide、Save 六个阶段。',
  'RAG 知识库用 LanceDB + 本地 embedding，减少攻略生成时的幻觉。',
  'MCP Server 让 Claude Desktop 等客户端可以直接调用 BudgetWings 工具层。',
  'SQLite、LangFuse、自动评估报告和静态站部署构成完整工程闭环。',
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
            一个围绕低价出行场景打造的 Agent Engineering 项目。
          </h1>
          <p className="max-w-2xl text-base leading-7 text-zinc-600 dark:text-zinc-300">
            旅行只是产品场景，真正想证明的是：我们能把多 Agent 编排、工具调用、RAG、质量评估、可观测性和自动部署做成一套长期可维护的系统。
          </p>
        </div>

        <img
          src="https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1400&q=80"
          alt="Travel planning"
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
        <h2 className="text-2xl font-bold text-zinc-950 dark:text-white">现在这个版本重点做了什么</h2>
        <ol className="grid gap-3 text-sm leading-7 text-zinc-600 dark:text-zinc-300">
          <li>1. 首页默认优先国内线路，不再把国际比价页放在主舞台。</li>
          <li>2. 查询入口改成真实输入：出发地、总预算、天数、时间窗、目标地关键词。</li>
          <li>3. 订票链接分成“可直接预订 / 平台搜索页 / 价格参考”，降低误导感。</li>
          <li>4. 预算不只看票价，还会把当地基础花费一起估算成“总预算”。</li>
        </ol>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="border border-zinc-200 px-5 py-5 dark:border-zinc-800">
          <h3 className="text-xl font-bold text-zinc-950 dark:text-white">为什么这更像真实产品</h3>
          <ul className="mt-4 grid gap-2 text-sm leading-7 text-zinc-600 dark:text-zinc-300">
            <li>- 从“展示 deal”往前走了一步，变成“帮用户做选择”。</li>
            <li>- 默认优先国内周末线，更符合中国用户真实决策路径。</li>
            <li>- 链接可信度被显式标注，不再把所有页面都包装成直接可买。</li>
          </ul>
        </div>
        <div className="border border-zinc-200 px-5 py-5 dark:border-zinc-800">
          <h3 className="text-xl font-bold text-zinc-950 dark:text-white">常用入口</h3>
          <ul className="mt-4 grid gap-2 text-sm leading-7 text-zinc-600 dark:text-zinc-300">
            <li>- `python cli.py run --city 深圳 --persona worker --top 5 --engine graph`</li>
            <li>- `python cli.py eval --city 深圳 --save`</li>
            <li>- `python -m mcp_server.server`</li>
            <li>- GitHub Pages 静态站自动部署</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
