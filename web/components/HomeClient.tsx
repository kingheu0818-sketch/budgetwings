'use client';

import Link from 'next/link';
import {useMemo, useState} from 'react';

import {DealCard} from './DealCard';
import {DisplayDeal, Persona, rankDeals} from '../lib/shared';

type HomeClientProps = {
  initialDeals: DisplayDeal[];
  updatedAt: string | null;
};

export function HomeClient({initialDeals, updatedAt}: HomeClientProps) {
  const [persona, setPersona] = useState<Persona>('worker');
  const [origin, setOrigin] = useState('全部');
  const [transport, setTransport] = useState('全部');
  const [tripScope, setTripScope] = useState<'all' | 'domestic' | 'international'>('all');
  const [maxPrice, setMaxPrice] = useState('1500');

  const originOptions = useMemo(
    () => ['全部', ...Array.from(new Set(initialDeals.map((deal) => deal.origin_label)))],
    [initialDeals]
  );
  const transportOptions = useMemo(
    () => ['全部', ...Array.from(new Set(initialDeals.map((deal) => deal.transport_mode)))],
    [initialDeals]
  );

  const deals = useMemo(() => {
    const max = Number(maxPrice || '99999');
    return rankDeals(initialDeals, persona)
      .filter((deal) => (origin === '全部' ? true : deal.origin_label === origin))
      .filter((deal) => (transport === '全部' ? true : deal.transport_mode === transport))
      .filter((deal) => {
        if (tripScope === 'all') return true;
        return tripScope === 'international' ? deal.isInternational : !deal.isInternational;
      })
      .filter((deal) => deal.price_cny_fen / 100 <= max);
  }, [initialDeals, maxPrice, origin, persona, transport, tripScope]);

  const updatedLabel = updatedAt
    ? new Intl.DateTimeFormat('zh-CN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(new Date(updatedAt))
    : '暂无更新记录';

  return (
    <main className="mx-auto grid max-w-7xl gap-10 px-4 py-6 sm:px-6 lg:px-8">
      <header className="grid gap-8 border-b border-zinc-200 pb-8 dark:border-zinc-800">
        <div className="grid gap-3">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-600 dark:text-emerald-300">
            BudgetWings
          </p>
          <h1 className="max-w-4xl text-4xl font-black leading-tight text-zinc-950 dark:text-white sm:text-6xl">
            低价出行 Agent，每天把能打的 deal 和可执行攻略一起整理好。
          </h1>
          <p className="max-w-3xl text-base leading-7 text-zinc-600 dark:text-zinc-300 sm:text-lg">
            这不是静态榜单。Scout 负责发现，Analyst 负责排序，Guide 负责把一条便宜路线变成真正能出发的计划。
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-sm">
          <button
            type="button"
            onClick={() => setPersona('worker')}
            className={personaButton(persona === 'worker')}
          >
            打工人模式
          </button>
          <button
            type="button"
            onClick={() => setPersona('student')}
            className={personaButton(persona === 'student')}
          >
            学生党模式
          </button>
          <Link href="/eval" className={navLinkClass}>
            评估面板
          </Link>
          <Link href="/status" className={navLinkClass}>
            系统状态
          </Link>
          <Link href="/about" className={navLinkClass}>
            项目说明
          </Link>
          <span className="ml-auto text-sm text-zinc-500 dark:text-zinc-400">最近更新：{updatedLabel}</span>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-4">
        <label className="grid gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
          出发城市
          <select
            className={inputClass}
            value={origin}
            onChange={(event) => setOrigin(event.target.value)}
          >
            {originOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
          交通方式
          <select
            className={inputClass}
            value={transport}
            onChange={(event) => setTransport(event.target.value)}
          >
            {transportOptions.map((option) => (
              <option key={option} value={option}>
                {option === 'flight'
                  ? '航班'
                  : option === 'train'
                    ? '火车 / 高铁'
                    : option === 'bus'
                      ? '大巴'
                      : option === 'carpool'
                        ? '拼车'
                        : option}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
          价格上限
          <input
            className={inputClass}
            inputMode="numeric"
            value={maxPrice}
            onChange={(event) => setMaxPrice(event.target.value)}
            placeholder="1500"
          />
        </label>

        <fieldset className="grid gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
          <legend>线路范围</legend>
          <div className="flex min-h-11 flex-wrap gap-2">
            {[
              ['all', '全部'],
              ['domestic', '国内'],
              ['international', '国际'],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setTripScope(value as 'all' | 'domestic' | 'international')}
                className={tripScopeButton(tripScope === value)}
              >
                {label}
              </button>
            ))}
          </div>
        </fieldset>
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        <div className="border border-zinc-200 px-4 py-4 dark:border-zinc-800">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">当前结果</p>
          <p className="mt-2 text-3xl font-black text-zinc-950 dark:text-white">{deals.length}</p>
        </div>
        <div className="border border-zinc-200 px-4 py-4 dark:border-zinc-800">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">不同目的地</p>
          <p className="mt-2 text-3xl font-black text-zinc-950 dark:text-white">
            {new Set(deals.map((deal) => deal.destination_label)).size}
          </p>
        </div>
        <div className="border border-zinc-200 px-4 py-4 dark:border-zinc-800">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">当前模式</p>
          <p className="mt-2 text-3xl font-black text-zinc-950 dark:text-white">
            {persona === 'worker' ? '打工人' : '学生党'}
          </p>
        </div>
      </section>

      {deals.length > 0 ? (
        <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {deals.map((deal) => (
            <DealCard key={deal.id} deal={deal} />
          ))}
        </section>
      ) : (
        <section className="grid min-h-52 place-items-center border border-dashed border-zinc-300 px-6 text-center dark:border-zinc-700">
          <div className="grid gap-3">
            <p className="text-lg font-semibold text-zinc-950 dark:text-white">这一组筛选条件下还没有合适的结果。</p>
            <p className="text-sm text-zinc-600 dark:text-zinc-300">放宽价格上限或切换线路范围，通常会更快找到能打的路线。</p>
          </div>
        </section>
      )}
    </main>
  );
}

const navLinkClass =
  'inline-flex min-h-10 items-center justify-center border border-zinc-300 px-4 text-sm font-semibold text-zinc-700 transition hover:border-zinc-500 hover:text-zinc-950 dark:border-zinc-700 dark:text-zinc-200 dark:hover:border-zinc-500';

const inputClass =
  'min-h-11 border border-zinc-300 bg-white px-3 text-sm text-zinc-950 outline-none transition focus:border-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-white dark:focus:border-zinc-400';

function personaButton(active: boolean): string {
  return active
    ? 'inline-flex min-h-10 items-center justify-center border border-zinc-900 bg-zinc-900 px-4 text-sm font-semibold text-white dark:border-white dark:bg-white dark:text-zinc-950'
    : navLinkClass;
}

function tripScopeButton(active: boolean): string {
  return active
    ? 'inline-flex min-h-10 items-center justify-center border border-emerald-500 bg-emerald-50 px-3 text-sm font-semibold text-emerald-700 dark:border-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-300'
    : 'inline-flex min-h-10 items-center justify-center border border-zinc-300 px-3 text-sm font-semibold text-zinc-700 dark:border-zinc-700 dark:text-zinc-200';
}
