import Link from 'next/link';
import {notFound} from 'next/navigation';

import {getDeal, getGuideIds, getGuideMarkdown, getLatestDeals} from '../../../lib/data';
import {formatDateLabel, priceYuan, transportLabel} from '../../../lib/shared';

export function generateStaticParams() {
  const ids = new Set<string>([
    ...getLatestDeals().map((deal) => deal.id),
    ...getGuideIds(),
  ]);
  return Array.from(ids).map((id) => ({id}));
}

export default function GuidePage({params}: {params: {id: string}}) {
  const deal = getDeal(params.id);
  if (!deal && !getGuideIds().includes(params.id)) {
    notFound();
  }

  const markdown = getGuideMarkdown(params.id);
  const sections = markdownToBlocks(markdown);

  return (
    <main className="mx-auto grid max-w-5xl gap-8 px-4 py-6 sm:px-6 lg:px-8">
      <Link href="/" className="text-sm font-semibold text-emerald-600 dark:text-emerald-300">
        返回首页
      </Link>

      {deal ? (
        <section className="grid gap-6 border border-zinc-200 dark:border-zinc-800 lg:grid-cols-[1.05fr_0.95fr]">
          <img src={deal.imageUrl} alt={deal.destinationLabel} className="h-72 w-full object-cover" />
          <div className="grid gap-4 p-5">
            <p className="text-sm font-semibold uppercase tracking-[0.12em] text-zinc-500">
              {transportLabel(deal.transport_mode)}
            </p>
            <h1 className="text-4xl font-black text-zinc-950 dark:text-white">
              {deal.originLabel} → {deal.destinationLabel}
            </h1>
            <p className="text-5xl font-black text-rose-600 dark:text-rose-400">
              ¥{priceYuan(deal)}
            </p>
            <div className="grid gap-2 text-sm text-zinc-600 dark:text-zinc-300">
              <p>
                日期：{formatDateLabel(deal.departure_date)}
                {deal.return_date ? ` - ${formatDateLabel(deal.return_date)}` : ' · 灵活返程'}
              </p>
              <p>{deal.operator ? `承运方：${deal.operator}` : '承运方：以出票平台为准'}</p>
              <p>{deal.isInternational ? '线路属性：国际' : '线路属性：国内'}</p>
            </div>
            <div className="flex gap-3">
              <a
                href={deal.booking_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-h-11 items-center justify-center border border-zinc-900 bg-zinc-900 px-4 text-sm font-semibold text-white dark:border-white dark:bg-white dark:text-zinc-950"
              >
                打开订票页
              </a>
              <Link
                href="/eval"
                className="inline-flex min-h-11 items-center justify-center border border-zinc-300 px-4 text-sm font-semibold text-zinc-700 dark:border-zinc-700 dark:text-zinc-200"
              >
                查看评估
              </Link>
            </div>
          </div>
        </section>
      ) : null}

      <article className="grid gap-6">
        {sections.map((block, index) => {
          if (block.type === 'h1') {
            return (
              <h2 key={`${block.type}-${index}`} className="text-3xl font-black text-zinc-950 dark:text-white">
                {block.text}
              </h2>
            );
          }
          if (block.type === 'h2') {
            return (
              <h3 key={`${block.type}-${index}`} className="text-2xl font-bold text-zinc-950 dark:text-white">
                {block.text}
              </h3>
            );
          }
          if (block.type === 'list') {
            return (
              <ul
                key={`${block.type}-${index}`}
                className="grid gap-2 border border-zinc-200 px-5 py-4 text-sm leading-7 text-zinc-700 dark:border-zinc-800 dark:text-zinc-200"
              >
                {block.items.map((item) => (
                  <li key={item}>- {item}</li>
                ))}
              </ul>
            );
          }
          return (
            <p
              key={`${block.type}-${index}`}
              className="max-w-4xl text-base leading-8 text-zinc-700 dark:text-zinc-200"
            >
              {block.text}
            </p>
          );
        })}
      </article>
    </main>
  );
}

type MarkdownBlock =
  | {type: 'h1'; text: string}
  | {type: 'h2'; text: string}
  | {type: 'paragraph'; text: string}
  | {type: 'list'; items: string[]};

function markdownToBlocks(markdown: string): MarkdownBlock[] {
  const lines = markdown.split('\n');
  const blocks: MarkdownBlock[] = [];
  let listBuffer: string[] = [];

  const flushList = () => {
    if (listBuffer.length > 0) {
      blocks.push({type: 'list', items: listBuffer});
      listBuffer = [];
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushList();
      continue;
    }
    if (line.startsWith('# ')) {
      flushList();
      blocks.push({type: 'h1', text: line.slice(2)});
      continue;
    }
    if (line.startsWith('## ')) {
      flushList();
      blocks.push({type: 'h2', text: line.slice(3)});
      continue;
    }
    if (line.startsWith('- ')) {
      listBuffer.push(line.slice(2));
      continue;
    }
    flushList();
    blocks.push({type: 'paragraph', text: line});
  }

  flushList();
  return blocks;
}
