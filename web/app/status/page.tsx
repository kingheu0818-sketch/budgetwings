import Link from 'next/link';

import {getStatusSnapshot} from '../../lib/data';

export default function StatusPage() {
  const status = getStatusSnapshot();

  return (
    <main className="mx-auto grid max-w-6xl gap-8 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex items-center justify-between gap-4">
        <Link href="/" className="text-sm font-semibold text-emerald-600 dark:text-emerald-300">
          返回首页
        </Link>
        <span className="text-sm text-zinc-500 dark:text-zinc-400">静态站构建时读取仓库数据</span>
      </div>

      <section className="grid gap-4">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-600 dark:text-emerald-300">
          System Status
        </p>
        <h1 className="text-4xl font-black text-zinc-950 dark:text-white sm:text-5xl">
          网站、数据、追踪和评估都在这里看状态。
        </h1>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard title="最新 deals" value={status.latestDealsFile ?? '无'} detail={status.latestDealsUpdatedAt} />
        <StatusCard title="最新 eval" value={status.latestEvalFile ?? '无'} detail={status.latestEvalUpdatedAt} />
        <StatusCard title="最新 trace" value={status.latestTraceFile ?? '无'} detail={status.latestTraceUpdatedAt} />
        <StatusCard title="SQLite" value={status.hasDatabase ? '已就绪' : '未发现'} detail="data/budgetwings.db" />
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <StatusCard title="本次构建可见 deal 数" value={String(status.dealsCount)} />
        <StatusCard title="本次构建可见 guide 数" value={String(status.guidesCount)} />
        <StatusCard title="部署方式" value="GitHub Pages" detail="push 到 main 后自动重新发布" />
      </section>
    </main>
  );
}

function StatusCard({
  title,
  value,
  detail,
}: {
  title: string;
  value: string;
  detail?: string | null;
}) {
  return (
    <article className="grid gap-2 border border-zinc-200 px-5 py-5 dark:border-zinc-800">
      <p className="text-sm text-zinc-500 dark:text-zinc-400">{title}</p>
      <p className="break-all text-2xl font-bold text-zinc-950 dark:text-white">{value}</p>
      {detail ? <p className="text-sm text-zinc-600 dark:text-zinc-300">{formatDetail(detail)}</p> : null}
    </article>
  );
}

function formatDetail(value: string): string {
  const date = new Date(value);
  if (!Number.isNaN(date.getTime()) && value.includes('T')) {
    return date.toLocaleString('zh-CN');
  }
  return value;
}
