import Link from 'next/link';

export default function AboutPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <Link href="/" className="text-sm font-semibold text-mint">返回首页</Link>
      <section className="mt-6 grid gap-6 md:grid-cols-[1.2fr_0.8fr] md:items-center">
        <div>
          <p className="font-semibold text-mint">BudgetWings</p>
          <h1 className="text-4xl font-black">AI 旅行智能体</h1>
          <p className="mt-4 leading-7 text-zinc-700 dark:text-zinc-300">
            从低价线索到短期攻略，Scout、Analyst、Guide 三个智能体一起把预算变成路线。
            打工人看周末效率，学生党看极限低价。
          </p>
        </div>
        <img
          src="https://source.unsplash.com/900x700/?travel,map"
          alt="Travel map"
          className="h-64 w-full rounded-lg object-cover"
        />
      </section>
    </main>
  );
}
