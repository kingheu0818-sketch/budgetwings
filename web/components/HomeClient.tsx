'use client';

import {useMemo, useState} from 'react';
import {DealCard} from './DealCard';
import {Deal, Persona, rankDeals} from '../lib/shared';

export function HomeClient({initialDeals}: {initialDeals: Deal[]}) {
  const [mode, setMode] = useState<Persona>('worker');
  const [origin, setOrigin] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const max = Number(maxPrice || '99999');
  const deals = useMemo(
    () =>
      rankDeals(initialDeals, mode)
        .filter((deal) => (origin ? deal.origin_city.includes(origin) : true))
        .filter((deal) => deal.price_cny_fen / 100 <= max),
    [initialDeals, max, mode, origin]
  );

  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-semibold text-mint">BudgetWings</p>
          <h1 className="text-3xl font-black sm:text-5xl">
            {mode === 'student' ? '最便宜能去哪？' : '这个周末去哪浪？'}
          </h1>
        </div>
        <nav className="flex flex-wrap gap-2">
          <button
            className="rounded-md border px-3 py-2"
            onClick={() => setMode('worker')}
            type="button"
          >
            打工人
          </button>
          <button
            className="rounded-md border px-3 py-2"
            onClick={() => setMode('student')}
            type="button"
          >
            学生党
          </button>
          <a className="rounded-md border px-3 py-2" href="/about">
            关于
          </a>
        </nav>
      </header>

      <section className="mb-6 grid gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900 sm:grid-cols-4">
        <label className="grid gap-1 text-sm">
          出发城市
          <input
            className="rounded-md border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
            onChange={(event) => setOrigin(event.target.value)}
            placeholder="深圳"
            value={origin}
          />
        </label>
        <label className="grid gap-1 text-sm">
          最高价
          <input
            className="rounded-md border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
            inputMode="numeric"
            onChange={(event) => setMaxPrice(event.target.value)}
            placeholder="500"
            value={maxPrice}
          />
        </label>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {deals.map((deal) => (
          <DealCard deal={deal} key={deal.id} />
        ))}
      </section>
    </main>
  );
}
