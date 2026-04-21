import Link from 'next/link';

import {
  type DisplayDeal,
  type Persona,
  bookingLinkCopy,
  estimateTripBudgetYuan,
  formatDateLabel,
  priceYuan,
  transportLabel,
} from '../lib/shared';

export function DealCard({
  deal,
  persona,
  tripDays,
  compact = false,
}: {
  deal: DisplayDeal;
  persona: Persona;
  tripDays: number;
  compact?: boolean;
}) {
  const price = priceYuan(deal);
  const totalBudget = estimateTripBudgetYuan(deal, persona, tripDays);
  const bookingCopy = bookingLinkCopy(deal.bookingLinkType);

  return (
    <article className="overflow-hidden border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <img src={deal.imageUrl} alt={deal.destinationLabel} className="h-48 w-full object-cover" />
      <div className="grid gap-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="grid gap-1">
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-zinc-500">
              {transportLabel(deal.transport_mode)}
            </p>
            <h2 className="text-xl font-semibold text-zinc-950 dark:text-white">
              {deal.originLabel} → {deal.destinationLabel}
            </h2>
            <p className="text-sm text-zinc-600 dark:text-zinc-300">
              {deal.isInternational ? '国际线路' : '国内线路'} · {bookingCopy.badge}
            </p>
          </div>
          <div className="grid justify-items-end gap-2 text-right">
            <div className="text-4xl font-black leading-none text-rose-600 dark:text-rose-400">
              ¥{price}
            </div>
            {price < 500 ? (
              <span className="border border-rose-200 bg-rose-50 px-2 py-1 text-xs font-semibold text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-300">
                低票价
              </span>
            ) : null}
          </div>
        </div>

        <div className="grid gap-1 text-sm leading-6 text-zinc-600 dark:text-zinc-300">
          <p>
            出发：{formatDateLabel(deal.departure_date)}
            {deal.return_date ? ` - ${formatDateLabel(deal.return_date)}` : ' · 单程'}
          </p>
          <p>预计总预算：¥{totalBudget}</p>
          <p>{deal.operator ? `承运方：${deal.operator}` : '承运方：以出票平台为准'}</p>
          {deal.hasHistoricalLow ? (
            <p className="font-medium text-emerald-700 dark:text-emerald-300">🔥 历史低价信号</p>
          ) : null}
          {!compact && deal.displayNotes ? (
            <p className="text-xs leading-6 text-zinc-500 dark:text-zinc-400">{deal.displayNotes}</p>
          ) : null}
          <p className="text-xs leading-6 text-zinc-500 dark:text-zinc-400">{bookingCopy.hint}</p>
        </div>

        <div className="flex gap-2">
          <Link
            href={`/guide/${deal.id}`}
            className="inline-flex min-h-10 items-center justify-center border border-zinc-900 bg-zinc-900 px-4 text-sm font-semibold text-white transition hover:bg-zinc-800 dark:border-white dark:bg-white dark:text-zinc-950 dark:hover:bg-zinc-200"
          >
            查看攻略
          </Link>
          <a
            href={deal.booking_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex min-h-10 items-center justify-center border border-zinc-300 px-4 text-sm font-semibold text-zinc-700 transition hover:border-zinc-500 hover:text-zinc-950 dark:border-zinc-700 dark:text-zinc-200 dark:hover:border-zinc-500"
          >
            {bookingCopy.buttonLabel}
          </a>
        </div>
      </div>
    </article>
  );
}
