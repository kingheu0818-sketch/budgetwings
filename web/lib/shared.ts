export type Persona = 'worker' | 'student';
export type TransportMode = 'flight' | 'train' | 'bus' | 'carpool';

export type Deal = {
  id: string;
  source: string;
  origin_city: string;
  origin_code?: string | null;
  destination_city: string;
  destination_code?: string | null;
  destination_country?: string | null;
  price_cny_fen: number;
  transport_mode: TransportMode;
  departure_date: string;
  return_date?: string | null;
  is_round_trip: boolean;
  operator?: string | null;
  booking_url: string;
  source_url?: string | null;
  notes?: string | null;
};

export type DisplayDeal = Deal & {
  origin_label: string;
  destination_label: string;
  country_label: string | null;
  display_notes: string | null;
  isInternational: boolean;
  hasHistoricalLow: boolean;
  imageUrl: string;
};

export type EvalReport = {
  metadata: {
    generated_at: string;
    cities: string[];
    persona: string;
    top_n: number;
    engine: string;
    source_mode: string;
    openai_key_present: boolean;
  };
  counts: {
    output_deals: number;
    golden_deals: number;
  };
  metrics: {
    price_accuracy: number;
    destination_recall: number;
    destination_precision: number;
    url_validity: number;
    data_freshness: number;
    diversity_score: number;
    matched_price_count: number;
    output_count: number;
    golden_count: number;
  };
  markdown?: string;
};

export type StatusSnapshot = {
  latestDealsFile: string | null;
  latestDealsUpdatedAt: string | null;
  latestEvalFile: string | null;
  latestEvalUpdatedAt: string | null;
  latestTraceFile: string | null;
  latestTraceUpdatedAt: string | null;
  dealsCount: number;
  guidesCount: number;
  hasDatabase: boolean;
};

const TEXT_REPLACEMENTS: Array<[string, string]> = [
  ['娣卞湷', '深圳'],
  ['鍖椾含', '北京'],
  ['涓婃捣', '上海'],
  ['骞垮窞', '广州'],
  ['鎴愰兘', '成都'],
  ['妗傛灄', '桂林'],
  ['閲嶅簡', '重庆'],
  ['婀涙睙', '湛江'],
  ['涓滀含', '东京'],
  ['棣栧皵', '首尔'],
  ['鏇艰胺', '曼谷'],
  ['娓呰繄', '清迈'],
  ['澶ч槳', '大阪'],
  ['涓変簹', '三亚'],
  ['娴峰彛', '海口'],
  ['鍗楀畞', '南宁'],
  ['璐甸槼', '贵阳'],
  ['馃敟', '🔥'],
  ['鈫?', '→'],
  ['楼', '¥'],
  ['路', ' · '],
  ['杩斿洖棣栭〉', '返回首页'],
  ['鏌ョ湅鏀荤暐', '查看攻略'],
  ['鍘昏绁?', '立即预订'],
  ['鍏充簬', '关于'],
  ['??', '未知'],
];

const INTERNATIONAL_DESTINATIONS = new Set([
  '东京',
  '首尔',
  '曼谷',
  '清迈',
  '大阪',
  '新加坡',
  '济州岛',
]);

const DESTINATION_IMAGES: Record<string, string> = {
  东京:
    'https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=1200&q=80',
  首尔:
    'https://images.unsplash.com/photo-1549693578-d683be217e58?auto=format&fit=crop&w=1200&q=80',
  曼谷:
    'https://images.unsplash.com/photo-1508009603885-50cf7c579365?auto=format&fit=crop&w=1200&q=80',
  清迈:
    'https://images.unsplash.com/photo-1552550018-5253c1b171e1?auto=format&fit=crop&w=1200&q=80',
  大阪:
    'https://images.unsplash.com/photo-1590559899731-a382839e5549?auto=format&fit=crop&w=1200&q=80',
  成都:
    'https://images.unsplash.com/photo-1526481280695-3c4691d7d0d1?auto=format&fit=crop&w=1200&q=80',
  重庆:
    'https://images.unsplash.com/photo-1518684079-3c830dcef090?auto=format&fit=crop&w=1200&q=80',
  三亚:
    'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80',
  湛江:
    'https://images.unsplash.com/photo-1519046904884-53103b34b206?auto=format&fit=crop&w=1200&q=80',
  海口:
    'https://images.unsplash.com/photo-1500375592092-40eb2168fd21?auto=format&fit=crop&w=1200&q=80',
};

export function normalizeText(value: string | null | undefined): string {
  if (!value) return '';
  let next = value;
  for (const [source, target] of TEXT_REPLACEMENTS) {
    next = next.split(source).join(target);
  }
  next = next.replace(/\uFFFD/g, '');
  return next.trim();
}

export function normalizeDeal(deal: Deal): DisplayDeal {
  const origin_label = normalizeText(deal.origin_city);
  const destination_label = normalizeText(deal.destination_city);
  const country_label = deal.destination_country ? normalizeText(deal.destination_country) : null;
  const display_notes = sanitizeNotes(deal.notes ?? null);
  const isInternational =
    INTERNATIONAL_DESTINATIONS.has(destination_label) || Boolean(country_label && country_label !== '中国');

  return {
    ...deal,
    origin_label,
    destination_label,
    country_label,
    display_notes,
    isInternational,
    hasHistoricalLow: (display_notes ?? '').includes('历史低价'),
    imageUrl: imageForDestination(destination_label),
  };
}

export function rankDeals(deals: DisplayDeal[], persona: Persona): DisplayDeal[] {
  const copy = [...deals];
  if (persona === 'student') {
    return copy.sort((a, b) => a.price_cny_fen - b.price_cny_fen);
  }
  return copy.sort((a, b) => {
    const dateDiff = a.departure_date.localeCompare(b.departure_date);
    return dateDiff || a.price_cny_fen - b.price_cny_fen;
  });
}

export function priceYuan(deal: Deal | DisplayDeal): number {
  return Math.round(deal.price_cny_fen / 100);
}

export function imageForDestination(destination: string): string {
  return (
    DESTINATION_IMAGES[destination] ??
    'https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=1200&q=80'
  );
}

export function formatDateLabel(dateText: string | null | undefined): string {
  if (!dateText) return '待确认';
  const date = new Date(dateText);
  if (Number.isNaN(date.getTime())) return normalizeText(dateText);
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
  }).format(date);
}

export function sanitizeNotes(notes: string | null): string | null {
  if (!notes) return null;
  const normalized = normalizeText(notes);
  if (!normalized) return null;
  if (looksCorrupted(normalized) && normalized.length > 40) {
    return '价格来自近期搜索结果，实际价格与舱位请以订票平台为准。';
  }
  if (normalized.includes('历史低价')) {
    return normalized;
  }
  return normalized;
}

export function looksCorrupted(text: string): boolean {
  const markers = ['鍘', '杩', '鈫', '浠', '鏃', '澶', '锛', '璇', '闂', '馃'];
  const hits = markers.filter((marker) => text.includes(marker)).length;
  return hits >= 2;
}

export function buildFallbackGuide(deal: DisplayDeal): string {
  const tripType = deal.is_round_trip ? '往返' : '单程';
  return [
    `# ${deal.destination_label} ${deal.isInternational ? '轻出境' : '周末短游'}攻略`,
    '',
    '## 出行摘要',
    '',
    `- 路线：${deal.origin_label} → ${deal.destination_label}`,
    `- 交通：${transportLabel(deal.transport_mode)}`,
    `- 票价：¥${priceYuan(deal)} ${tripType}`,
    `- 出发：${deal.departure_date}`,
    deal.return_date ? `- 返回：${deal.return_date}` : '- 返回：按需灵活安排',
    '',
    '## 签证与证件',
    '',
    deal.isInternational
      ? '- 这是出境行程，出发前请再次核对签证、护照有效期和航空公司登机要求。'
      : '- 这是国内行程，携带身份证并预留机场/车站安检时间即可。',
    '',
    '## 行程建议',
    '',
    '- 上午：抵达后先办理入住或寄存行李，优先去最核心的地标片区。',
    '- 下午：安排一条步行友好的主线，保留拍照、咖啡或午餐时间。',
    '- 晚上：选择评价稳定的夜市、商圈或景观带，别把节奏排太满。',
    '',
    '## 预算建议',
    '',
    '- 住宿：打工人建议 200-500 元/晚，学生党建议 30-120 元/晚。',
    '- 餐饮：本地小馆和市场往往更稳，先看评价再决定要不要排队。',
    '- 交通：如果只有两天，打车/网约车通常比频繁换乘更省心。',
    '',
    '## 预订提醒',
    '',
    `- 订票链接：${deal.booking_url}`,
    '- 价格和库存变化很快，最终以下单页面为准。',
  ].filter(Boolean).join('\n');
}

export function transportLabel(mode: TransportMode): string {
  switch (mode) {
    case 'flight':
      return '航班';
    case 'train':
      return '火车 / 高铁';
    case 'bus':
      return '大巴';
    case 'carpool':
      return '拼车';
    default:
      return mode;
  }
}

export function metricPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
