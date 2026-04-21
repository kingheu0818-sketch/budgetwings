import Link from 'next/link';

import {getLatestEvalReport} from '../../lib/data';
import {metricPercent} from '../../lib/shared';

const metricCopy: Array<[keyof NonNullable<ReturnType<typeof getLatestEvalReport>>['metrics'], string]> = [
  ['price_accuracy', '价格是否落在合理区间（±30%）'],
  ['destination_recall', '标准答案中的目的地找回了多少'],
  ['destination_precision', '当前输出中有多少属于标准答案'],
  ['url_validity', '订票链接是否为可用 https 链接'],
  ['data_freshness', '出发日期是否仍在未来'],
  ['diversity_score', '目的地覆盖是否足够分散'],
];

export default function EvalPage() {
  const report = getLatestEvalReport();

  return (
    <main className="mx-auto grid max-w-6xl gap-8 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex items-center justify-between gap-4">
        <Link href="/" className="text-sm font-semibold text-emerald-600 dark:text-emerald-300">
          返回首页
        </Link>
        {report ? (
          <span className="text-sm text-zinc-500 dark:text-zinc-400">
            最近评估：{new Date(report.metadata.generated_at).toLocaleString('zh-CN')}
          </span>
        ) : null}
      </div>

      <section className="grid gap-4">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-600 dark:text-emerald-300">
          Evaluation
        </p>
        <h1 className="text-4xl font-black text-zinc-950 dark:text-white sm:text-5xl">
          每次改 prompt 或换模型后，这里会直接告诉我们质量有没有变好。
        </h1>
      </section>

      {report ? (
        <>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {metricCopy.map(([key, description]) => (
              <article key={key} className="border border-zinc-200 px-5 py-5 dark:border-zinc-800">
                <p className="text-sm text-zinc-500 dark:text-zinc-400">{key}</p>
                <p className="mt-2 text-4xl font-black text-zinc-950 dark:text-white">
                  {metricPercent(report.metrics[key])}
                </p>
                <p className="mt-3 text-sm leading-7 text-zinc-600 dark:text-zinc-300">{description}</p>
              </article>
            ))}
          </section>

          <section className="grid gap-4 border border-zinc-200 px-5 py-5 dark:border-zinc-800 lg:grid-cols-3">
            <div>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">评估城市</p>
              <p className="mt-2 text-2xl font-bold text-zinc-950 dark:text-white">
                {report.metadata.cities.join('、') || '未记录'}
              </p>
            </div>
            <div>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">评估来源</p>
              <p className="mt-2 text-2xl font-bold text-zinc-950 dark:text-white">{report.metadata.source_mode}</p>
            </div>
            <div>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">样本量</p>
              <p className="mt-2 text-2xl font-bold text-zinc-950 dark:text-white">
                {report.counts.output_deals} / {report.counts.golden_deals}
              </p>
            </div>
          </section>

          <section className="grid gap-4 border border-zinc-200 px-5 py-5 dark:border-zinc-800">
            <h2 className="text-2xl font-bold text-zinc-950 dark:text-white">为什么这个页面重要</h2>
            <p className="max-w-4xl text-base leading-8 text-zinc-600 dark:text-zinc-300">
              Agent 项目的难点不在“能不能跑”，而在“改完之后是不是更好”。这个页面把价格准确度、目的地覆盖率和链接有效性放在一起，让模型切换、prompt 调整和工具升级都有可比较的结果。
            </p>
          </section>
        </>
      ) : (
        <section className="grid min-h-60 place-items-center border border-dashed border-zinc-300 px-6 text-center dark:border-zinc-700">
          <div className="grid gap-3">
            <p className="text-lg font-semibold text-zinc-950 dark:text-white">还没有评估报告。</p>
            <p className="text-sm text-zinc-600 dark:text-zinc-300">
              先运行 `python cli.py eval --city 深圳 --save`，这里就会自动显示最新结果。
            </p>
          </div>
        </section>
      )}
    </main>
  );
}
