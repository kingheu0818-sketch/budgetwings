import Link from 'next/link';
import {getDeal, getGuideMarkdown, getGuides, getLatestDeals} from '../../../lib/data';

export function generateStaticParams() {
  const ids = new Set<string>([
    ...getLatestDeals().map((deal) => deal.id),
    ...getGuides().map((file) => file.replace(/\.md$/, ''))
  ]);
  return Array.from(ids).map((id) => ({id}));
}

function renderMarkdown(markdown: string) {
  return markdown.split('\n').map((line, index) => {
    if (line.startsWith('# ')) {
      return <h1 className="mt-2 text-3xl font-black" key={index}>{line.slice(2)}</h1>;
    }
    if (line.startsWith('## ')) {
      return <h2 className="mt-6 text-xl font-bold" key={index}>{line.slice(3)}</h2>;
    }
    if (line.startsWith('- ')) {
      return <li className="ml-5 list-disc" key={index}>{line.slice(2)}</li>;
    }
    if (!line.trim()) {
      return <div className="h-2" key={index} />;
    }
    return <p className="leading-7 text-zinc-700 dark:text-zinc-300" key={index}>{line}</p>;
  });
}

export default function GuidePage({params}: {params: {id: string}}) {
  const deal = getDeal(params.id);
  const markdown = getGuideMarkdown(params.id);

  return (
    <main className="mx-auto max-w-3xl px-4 py-6">
      <Link href="/" className="text-sm font-semibold text-mint">返回首页</Link>
      {deal ? (
        <section className="my-6 overflow-hidden rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
          <img
            src={`https://source.unsplash.com/1200x650/?${encodeURIComponent(deal.destination_city)},city`}
            alt={`${deal.destination_city} city`}
            className="h-56 w-full object-cover"
          />
          <div className="p-5">
            <p className="text-sm text-zinc-500">{deal.origin_city} → {deal.destination_city}</p>
            <p className="text-4xl font-black text-coral">¥{Math.round(deal.price_cny_fen / 100)}</p>
          </div>
        </section>
      ) : null}
      <article className="prose prose-zinc max-w-none dark:prose-invert">
        {renderMarkdown(markdown)}
      </article>
    </main>
  );
}
