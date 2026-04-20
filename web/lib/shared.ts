export type Persona = 'worker' | 'student';

export type Deal = {
  id: string;
  source: string;
  origin_city: string;
  origin_code?: string | null;
  destination_city: string;
  destination_code?: string | null;
  destination_country?: string | null;
  price_cny_fen: number;
  transport_mode: 'flight' | 'train' | 'bus' | 'carpool';
  departure_date: string;
  return_date?: string | null;
  is_round_trip: boolean;
  operator?: string | null;
  booking_url: string;
  notes?: string | null;
};

export function rankDeals(deals: Deal[], persona: Persona): Deal[] {
  const copy = [...deals];
  if (persona === 'student') {
    return copy.sort((a, b) => a.price_cny_fen - b.price_cny_fen);
  }
  return copy.sort((a, b) => {
    const dateDiff = a.departure_date.localeCompare(b.departure_date);
    return dateDiff || a.price_cny_fen - b.price_cny_fen;
  });
}

export function priceYuan(deal: Deal): number {
  return Math.round(deal.price_cny_fen / 100);
}

export function imageForDeal(deal: Deal): string {
  const city = encodeURIComponent(deal.destination_city);
  return `https://source.unsplash.com/900x600/?${city},travel`;
}
