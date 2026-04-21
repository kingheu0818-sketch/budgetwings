import Link from 'next/link';

export default function NotFound() {
  return (
    <main className="mx-auto grid min-h-screen max-w-3xl place-items-center px-4 py-12 text-center">
      <div className="grid gap-4">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-600 dark:text-emerald-300">
          404
        </p>
        <h1 className="text-4xl font-black text-zinc-950 dark:text-white">这条线路暂时还没上线。</h1>
        <p className="text-base leading-7 text-zinc-600 dark:text-zinc-300">
          可能是攻略尚未生成，也可能是页面链接已经过期。
        </p>
        <div>
          <Link
            href="/"
            className="inline-flex min-h-11 items-center justify-center border border-zinc-900 bg-zinc-900 px-4 text-sm font-semibold text-white dark:border-white dark:bg-white dark:text-zinc-950"
          >
            回到首页
          </Link>
        </div>
      </div>
    </main>
  );
}
