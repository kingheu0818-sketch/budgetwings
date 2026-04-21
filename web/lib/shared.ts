export type Persona = 'worker' | 'student';
export type TransportMode = 'flight' | 'train' | 'bus' | 'carpool';
export type TripScope = 'domestic' | 'all';
export type DepartureWindow = 'weekend' | '7d' | '30d' | '90d';
export type BookingLinkType = 'direct_booking' | 'search_page' | 'reference_only';

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
  originLabel: string;
  destinationLabel: string;
  countryLabel: string | null;
  displayNotes: string | null;
  isInternational: boolean;
  hasHistoricalLow: boolean;
  imageUrl: string;
  bookingLinkType: BookingLinkType;
  bookingHost: string;
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

export type QueryInput = {
  origin: string;
  destinationKeyword: string;
  budgetYuan: number | null;
  tripDays: number;
  transport: TransportMode | 'all';
  departureWindow: DepartureWindow;
  tripScope: TripScope;
  persona: Persona;
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
  ['浠锋牸鍙傝€冭嚜', '价格参考自'],
  ['鍘嗗彶浣庝环', '历史低价'],
  ['瀹為檯浠锋牸璇蜂互璁㈢エ骞冲彴涓哄噯', '实际价格请以订票平台为准'],
  ['馃敟', '🔥'],
  ['鈫?', '→'],
  ['楼', '¥'],
  ['路', ' · '],
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
  桂林:
    'https://images.unsplash.com/photo-1518384401463-d3876163c195?auto=format&fit=crop&w=1200&q=80',
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
  const originLabel = normalizeText(deal.origin_city);
  const destinationLabel = normalizeText(deal.destination_city);
  const countryLabel = deal.destination_country ? normalizeText(deal.destination_country) : null;
  const displayNotes = sanitizeNotes(deal.notes ?? null);
  const bookingHost = safeHost(deal.booking_url);
  const isInternational =
    INTERNATIONAL_DESTINATIONS.has(destinationLabel) ||
    Boolean(countryLabel && countryLabel !== '中国');

  return {
    ...deal,
    originLabel,
    destinationLabel,
    countryLabel,
    displayNotes,
    isInternational,
    hasHistoricalLow: (displayNotes ?? '').includes('历史低价'),
    imageUrl: imageForDestination(destinationLabel),
    bookingLinkType: classifyBookingLink(deal.booking_url, isInternational),
    bookingHost,
  };
}

export function queryDeals(deals: DisplayDeal[], input: QueryInput): DisplayDeal[] {
  const normalizedKeyword = input.destinationKeyword.trim().toLowerCase();
  const ranked = rankDeals(deals, input.persona);

  return ranked.filter((deal) => {
    if (input.origin !== '全部' && deal.originLabel !== input.origin) return false;
    if (input.tripScope === 'domestic' && deal.isInternational) return false;
    if (input.transport !== 'all' && deal.transport_mode !== input.transport) return false;
    if (normalizedKeyword) {
      const haystack = `${deal.destinationLabel} ${deal.countryLabel ?? ''}`.toLowerCase();
      if (!haystack.includes(normalizedKeyword)) return false;
    }
    if (!matchesDepartureWindow(deal.departure_date, input.departureWindow, input.persona)) return false;
    if (input.budgetYuan !== null && estimateTripBudgetYuan(deal, input.persona, input.tripDays) > input.budgetYuan) {
      return false;
    }
    return true;
  });
}

export function rankDeals(deals: DisplayDeal[], persona: Persona): DisplayDeal[] {
  return [...deals].sort((left, right) => {
    const scopeScore = Number(left.isInternational) - Number(right.isInternational);
    if (scopeScore !== 0) return scopeScore;

    const linkScore = bookingLinkPriority(left.bookingLinkType) - bookingLinkPriority(right.bookingLinkType);
    if (linkScore !== 0) return linkScore;

    const transportScore = transportPriority(left.transport_mode, persona) - transportPriority(right.transport_mode, persona);
    if (transportScore !== 0) return transportScore;

    const weekendScore = Number(!isWeekendFriendly(left.departure_date)) - Number(!isWeekendFriendly(right.departure_date));
    if (weekendScore !== 0) return weekendScore;

    const dateDiff = left.departure_date.localeCompare(right.departure_date);
    if (dateDiff !== 0) return dateDiff;

    return left.price_cny_fen - right.price_cny_fen;
  });
}

export function estimateTripBudgetYuan(
  deal: DisplayDeal,
  persona: Persona,
  tripDays: number
): number {
  const ticket = priceYuan(deal);
  const localDailyCost = persona === 'worker'
    ? deal.isInternational
      ? 550
      : 380
    : deal.isInternational
      ? 300
      : 180;

  return ticket + localDailyCost * Math.max(tripDays, 1);
}

export function priceYuan(deal: Deal | DisplayDeal): number {
  return Math.round(deal.price_cny_fen / 100);
}

export function formatDateLabel(dateText: string | null | undefined): string {
  if (!dateText) return '待确认';
  const date = new Date(dateText);
  if (Number.isNaN(date.getTime())) return normalizeText(dateText);
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    weekday: 'short',
  }).format(date);
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

export function imageForDestination(destination: string): string {
  return (
    DESTINATION_IMAGES[destination] ??
    'https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=1200&q=80'
  );
}

export function sanitizeNotes(notes: string | null): string | null {
  if (!notes) return null;
  const normalized = normalizeText(notes);
  if (!normalized) return null;
  if (looksCorrupted(normalized) && normalized.length > 40) {
    return '价格来自近期搜索结果，最终库存和支付币种请以出票页面为准。';
  }
  return normalized;
}

export function looksCorrupted(text: string): boolean {
  const markers = ['鍘', '杩', '鈫', '浠', '鏃', '澶', '锛', '璇', '闂', '馃'];
  const hits = markers.filter((marker) => text.includes(marker)).length;
  return hits >= 2;
}

export function bookingLinkCopy(linkType: BookingLinkType): {
  badge: string;
  hint: string;
  buttonLabel: string;
} {
  switch (linkType) {
    case 'direct_booking':
      return {
        badge: '可直接预订',
        hint: '链接更接近国内常用出票平台，可直接核价和下单。',
        buttonLabel: '打开预订页',
      };
    case 'search_page':
      return {
        badge: '平台搜索页',
        hint: '这是平台搜索结果页，价格大概率可信，但下单前还要再点一步。',
        buttonLabel: '查看平台页',
      };
    case 'reference_only':
      return {
        badge: '价格参考',
        hint: '这是比价页或海外页面，适合参考，不保证支付和出票体验。',
        buttonLabel: '查看参考页',
      };
    default:
      return {
        badge: '待确认',
        hint: '价格需要二次核实。',
        buttonLabel: '查看详情',
      };
  }
}

export function buildFallbackGuide(deal: DisplayDeal): string {
  const tripType = deal.is_round_trip ? '往返' : '单程';
  return [
    `# ${deal.destinationLabel}${deal.isInternational ? '轻出境' : '周末短游'}攻略`,
    '',
    '## 出行摘要',
    '',
    `- 路线：${deal.originLabel} → ${deal.destinationLabel}`,
    `- 交通：${transportLabel(deal.transport_mode)}`,
    `- 票价：¥${priceYuan(deal)} ${tripType}`,
    `- 出发：${deal.departure_date}`,
    deal.return_date ? `- 返回：${deal.return_date}` : '- 返回：按需灵活安排',
    '',
    '## 适合怎么用',
    '',
    deal.isInternational
      ? '- 这条路线更适合你已经想好要出境，再来做价格对比和线路决策。'
      : '- 这条路线更适合说走就走的两到三天国内短旅行。',
    '- 先确认出发日期和总预算，再决定要不要立刻下单。',
    '',
    '## 预订提醒',
    '',
    `- 链接类型：${bookingLinkCopy(deal.bookingLinkType).badge}`,
    `- 订票链接：${deal.booking_url}`,
    '- 价格和库存变化很快，最终以下单页为准。',
  ].filter(Boolean).join('\n');
}

export function isWeekendFriendly(dateText: string): boolean {
  const date = new Date(dateText);
  if (Number.isNaN(date.getTime())) return false;
  const day = date.getDay();
  return day === 5 || day === 6 || day === 0;
}

function matchesDepartureWindow(
  dateText: string,
  window: DepartureWindow,
  persona: Persona
): boolean {
  const date = new Date(dateText);
  if (Number.isNaN(date.getTime())) return false;
  const now = new Date();
  const diffDays = Math.ceil((date.getTime() - now.getTime()) / (24 * 60 * 60 * 1000));
  if (diffDays < 0) return false;

  if (window === '7d') return diffDays <= 7;
  if (window === '30d') return diffDays <= 30;
  if (window === '90d') return diffDays <= 90;

  if (persona === 'worker') return diffDays <= 21 && isWeekendFriendly(dateText);
  return diffDays <= 30;
}

function bookingLinkPriority(linkType: BookingLinkType): number {
  switch (linkType) {
    case 'direct_booking':
      return 0;
    case 'search_page':
      return 1;
    case 'reference_only':
      return 2;
    default:
      return 3;
  }
}

function transportPriority(mode: TransportMode, persona: Persona): number {
  if (persona === 'worker') {
    if (mode === 'flight') return 0;
    if (mode === 'train') return 1;
    if (mode === 'bus') return 2;
    return 3;
  }

  if (mode === 'train') return 0;
  if (mode === 'bus') return 1;
  if (mode === 'flight') return 2;
  return 3;
}

function classifyBookingLink(url: string, isInternational: boolean): BookingLinkType {
  const host = safeHost(url);

  if (host.includes('ctrip.com') || host.includes('qunar.com') || host.includes('12306.cn')) {
    return 'direct_booking';
  }

  if (host.includes('trip.com')) {
    return isInternational || host.startsWith('hk.') ? 'reference_only' : 'search_page';
  }

  if (
    host.includes('skyscanner') ||
    host.includes('tianxun') ||
    host.includes('google.') ||
    host.includes('wego.')
  ) {
    return 'reference_only';
  }

  return isInternational ? 'reference_only' : 'search_page';
}

function safeHost(url: string): string {
  try {
    return new URL(url).host.toLowerCase();
  } catch {
    return '';
  }
}
