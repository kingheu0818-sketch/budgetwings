import Link from 'next/link';
import {Deal, imageForDeal, priceYuan} from '../lib/shared';

export function DealCard({deal}: {deal: Deal}) {
  const price = priceYuan(deal);
  return (
    <article className="overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <img
        src={imageForDeal(deal)}
        alt={`${deal.destination_city} travel`}
        className="h-40 w-full object-cover"
      />
      <div className="space-y-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">{deal.transport_mode}</p>
            <h2 className="text-xl font-bold">
              {deal.origin_city} → {deal.destination_city}
            </h2>
          </div>
          {price < 500 ? (
            <span className="rounded-md bg-coral px-2 py-1 text-sm font-bold text-white">🔥</span>
          ) : null}
        </div>
        <div className="text-4xl font-black text-coral">¥{price}</div>
        <p className="text-sm text-zinc-600 dark:text-zinc-300">
          {deal.departure_date}
          {deal.return_date ? ` - ${deal.return_date}` : ''}
          {deal.operator ? ` · ${deal.operator}` : ''}
        </p>
        <div className="flex gap-2">
          <Link
            href={`/guide/${deal.id}`}
            className="rounded-md bg-ink px-3 py-2 text-sm font-semibold text-white dark:bg-white dark:text-ink"
          >
            查看攻略
          </Link>
          <a
            href={deal.booking_url}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold dark:border-zinc-700"
          >
            去订票
          </a>
        </div>
      </div>
    </article>
  );
}
