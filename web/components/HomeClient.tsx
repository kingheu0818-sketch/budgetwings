'use client';

import Link from 'next/link';
import {useMemo, useState} from 'react';

import {DealCard} from './DealCard';
import {
  type DepartureWindow,
  type DisplayDeal,
  type Persona,
  type QueryInput,
  bookingLinkCopy,
  estimateTripBudgetYuan,
  queryDeals,
  transportLabel,
} from '../lib/shared';

type HomeClientProps = {
  initialDeals: DisplayDeal[];
  updatedAt: string | null;
};

const DEPARTURE_OPTIONS: Array<{value: DepartureWindow; label: string}> = [
  {value: 'weekend', label: '周末优先'},
  {value: '7d', label: '7 天内'},
  {value: '30d', label: '30 天内'},
  {value: '90d', label: '90 天内'},
];

const TRIP_DAYS = [2, 3, 4, 5];

export function HomeClient({initialDeals, updatedAt}: HomeClientProps) {
  const [persona, setPersona] = useState<Persona>('worker');
  const [origin, setOrigin] = useState('全部');
  const [destinationKeyword, setDestinationKeyword] = useState('');
  const [budget, setBudget] = useState('1800');
  const [tripDays, setTripDays] = useState(2);
  const [transport, setTransport] = useState<QueryInput['transport']>('all');
  const [departureWindow, setDepartureWindow] = useState<DepartureWindow>('weekend');
  const [domesticOnly, setDomesticOnly] = useState(true);

  const originOptions = useMemo(
    () => ['全部', ...Array.from(new Set(initialDeals.map((deal) => deal.originLabel)))],
    [initialDeals]
  );

  const query = useMemo<QueryInput>(
    () => ({
      origin,
      destinationKeyword,
      budgetYuan: Number.isFinite(Number(budget)) && budget.trim() ? Number(budget) : null,
      tripDays,
      transport,
      departureWindow,
      tripScope: domesticOnly ? 'domestic' : 'all',
      persona,
    }),
    [budget, departureWindow, destinationKeyword, domesticOnly, origin, persona, transport, tripDays]
  );

  const deals = useMemo(() => queryDeals(initialDeals, query), [initialDeals, query]);
  const primaryDeals = deals.slice(0, 3);
  const backupDeals = deals.slice(3, 9);
  const domesticCount = deals.filter((deal) => !deal.isInternational).length;
  const directBookingCount = deals.filter((deal) => deal.bookingLinkType === 'direct_booking').length;

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
          <h1 className="max-w-5xl text-4xl font-black leading-tight text-zinc-950 dark:text-white sm:text-6xl">
            先把国内低价周末旅行做扎实，再决定要不要出境。
          </h1>
          <p className="max-w-3xl text-base leading-7 text-zinc-600 dark:text-zinc-300 sm:text-lg">
            这版首页默认优先国内线路、常用平台和总预算可控的路线。你可以直接输入出发地、预算、天数和目标地关键词，拿到更接近真实可用的推荐。
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

      <section className="grid gap-4 border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950 lg:grid-cols-6">
        <label className="grid gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
          从哪里出发
          <select className={inputClass} value={origin} onChange={(event) => setOrigin(event.target.value)}>
            {originOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
          想去哪里
          <input
            className={inputClass}
            value={destinationKeyword}
            onChange={(event) => setDestinationKeyword(event.target.value)}
            placeholder="例如：重庆、三亚、成都"
          />
        </label>

        <label className="grid gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
          总预算
          <input
            className={inputClass}
            inputMode="numeric"
            value={budget}
            onChange={(event) => setBudget(event.target.value)}
            placeholder="1800"
          />
        </label>

        <label className="grid gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
          行程天数
          <select
            className={inputClass}
            value={String(tripDays)}
            onChange={(event) => setTripDays(Number(event.target.value))}
          >
            {TRIP_DAYS.map((days) => (
              <option key={days} value={days}>
                {days} 天
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
          出发时间
          <select
            className={inputClass}
            value={departureWindow}
            onChange={(event) => setDepartureWindow(event.target.value as DepartureWindow)}
          >
            {DEPARTURE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
          交通方式
          <select
            className={inputClass}
            value={transport}
            onChange={(event) => setTransport(event.target.value as QueryInput['transport'])}
          >
            <option value="all">全部</option>
            <option value="flight">航班</option>
            <option value="train">火车 / 高铁</option>
            <option value="bus">大巴</option>
            <option value="carpool">拼车</option>
          </select>
        </label>

        <div className="col-span-full flex flex-wrap items-center gap-3 border-t border-zinc-200 pt-4 text-sm dark:border-zinc-800">
          <button
            type="button"
            onClick={() => setDomesticOnly((value) => !value)}
            className={domesticOnly ? toggleActiveClass : toggleClass}
          >
            {domesticOnly ? '国内优先：开启' : '国内优先：关闭'}
          </button>
          <span className="text-zinc-500 dark:text-zinc-400">
            当前默认会优先展示国内线路和国内用户更容易直接下单的平台。
          </span>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-4">
        <SummaryCard title="符合条件" value={String(deals.length)} detail="已经过预算、时间和国内优先筛选" />
        <SummaryCard title="国内线路" value={String(domesticCount)} detail="这批结果里更适合周末出发的线路数" />
        <SummaryCard title="可直接预订" value={String(directBookingCount)} detail="链接更接近国内常用出票平台" />
        <SummaryCard
          title="查询偏好"
          value={persona === 'worker' ? '打工人' : '学生党'}
          detail={persona === 'worker' ? '周末和效率优先' : '总预算和性价比优先'}
        />
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="grid gap-5">
          <div className="grid gap-2">
            <h2 className="text-2xl font-bold text-zinc-950 dark:text-white">现在最值得看的 3 条</h2>
            <p className="text-sm leading-7 text-zinc-600 dark:text-zinc-300">
              这里优先把国内、预算内、出发时间更合适、链接更可信的路线放到前面。
            </p>
          </div>

          {primaryDeals.length > 0 ? (
            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
              {primaryDeals.map((deal) => (
                <DealCard key={deal.id} deal={deal} persona={persona} tripDays={tripDays} />
              ))}
            </div>
          ) : (
            <EmptyState />
          )}
        </div>

        <aside className="grid gap-4 border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-xl font-bold text-zinc-950 dark:text-white">使用提醒</h2>
          <div className="grid gap-3 text-sm leading-7 text-zinc-600 dark:text-zinc-300">
            <p>
              预算筛选按 <strong>总预算</strong> 计算，不只是交通票价。系统会把大交通和当地的基础花销一起估算。
            </p>
            <p>
              国际线路仍然可以看，但默认会往后放，因为很多比价页、港币页或海外平台对国内用户并不够顺手。
            </p>
            <p>
              如果你只想这周末就出发，优先看 <strong>火车 / 高铁</strong> 和 <strong>国内航班</strong>。
            </p>
          </div>

          {primaryDeals[0] ? (
            <div className="border border-zinc-200 p-4 text-sm leading-7 dark:border-zinc-800">
              <p className="font-semibold text-zinc-950 dark:text-white">首选路线提示</p>
              <p className="mt-2">
                {primaryDeals[0].originLabel} → {primaryDeals[0].destinationLabel}
              </p>
              <p>预计总花费：¥{estimateTripBudgetYuan(primaryDeals[0], persona, tripDays)}</p>
              <p className="mt-2 text-zinc-500 dark:text-zinc-400">
                {bookingLinkCopy(primaryDeals[0].bookingLinkType).hint}
              </p>
            </div>
          ) : null}
        </aside>
      </section>

      {backupDeals.length > 0 ? (
        <section className="grid gap-5">
          <div className="grid gap-2">
            <h2 className="text-2xl font-bold text-zinc-950 dark:text-white">预算内备选</h2>
            <p className="text-sm leading-7 text-zinc-600 dark:text-zinc-300">
              如果你想多看看路线，这里保留一批同样满足条件、但优先级略低的备选。
            </p>
          </div>
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {backupDeals.map((deal) => (
              <DealCard key={deal.id} deal={deal} persona={persona} tripDays={tripDays} compact />
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}

function SummaryCard({
  title,
  value,
  detail,
}: {
  title: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="border border-zinc-200 bg-white px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-sm text-zinc-500 dark:text-zinc-400">{title}</p>
      <p className="mt-2 text-3xl font-black text-zinc-950 dark:text-white">{value}</p>
      <p className="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-300">{detail}</p>
    </div>
  );
}

function EmptyState() {
  return (
    <section className="grid min-h-56 place-items-center border border-dashed border-zinc-300 px-6 text-center dark:border-zinc-700">
      <div className="grid gap-3">
        <p className="text-lg font-semibold text-zinc-950 dark:text-white">这一组条件下还没有合适的路线。</p>
        <p className="text-sm text-zinc-600 dark:text-zinc-300">
          试着放宽总预算、把出发时间改成 30 天内，或者先取消目标地关键词。
        </p>
      </div>
    </section>
  );
}

const navLinkClass =
  'inline-flex min-h-10 items-center justify-center border border-zinc-300 px-4 text-sm font-semibold text-zinc-700 transition hover:border-zinc-500 hover:text-zinc-950 dark:border-zinc-700 dark:text-zinc-200 dark:hover:border-zinc-500';

const inputClass =
  'min-h-11 border border-zinc-300 bg-white px-3 text-sm text-zinc-950 outline-none transition focus:border-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-white dark:focus:border-zinc-400';

const toggleClass =
  'inline-flex min-h-10 items-center justify-center border border-zinc-300 px-4 text-sm font-semibold text-zinc-700 transition hover:border-zinc-500 hover:text-zinc-950 dark:border-zinc-700 dark:text-zinc-200';

const toggleActiveClass =
  'inline-flex min-h-10 items-center justify-center border border-emerald-500 bg-emerald-50 px-4 text-sm font-semibold text-emerald-700 dark:border-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-300';

function personaButton(active: boolean): string {
  return active
    ? 'inline-flex min-h-10 items-center justify-center border border-zinc-900 bg-zinc-900 px-4 text-sm font-semibold text-white dark:border-white dark:bg-white dark:text-zinc-950'
    : navLinkClass;
}
