# Guide Template Format

Guide templates live under `guides/` as YAML files. Each file represents one destination and must match `models.guide.GuideTemplate`.

```yaml
destination:
  city: Chiang Mai
  country: Thailand
  tags: [Southeast Asia, temples, food]
visa:
  cn_passport: "Visa policy note for Chinese passport holders."
  tips: "Extra preparation tips."
weather:
  best_months: [11, 12, 1, 2]
  rainy_season: [6, 7, 8, 9]
  current: "{{ dynamic_weather_data }}"
transport:
  from_airport: "How to leave the airport cheaply."
  in_city: "How to move around the city."
highlights:
  free:
    - Free city walk
  paid:
    - Paid attraction
food:
  budget:
    - Student-friendly meal
  midrange:
    - Worker-friendly meal
accommodation:
  budget: "Hostel or capsule range."
  midrange: "Budget hotel or homestay range."
itinerary_templates:
  2day:
    day1: "Morning -> afternoon -> night"
    day2: "Morning -> return"
budget_estimate:
  student_2day: "CNY 300-500 excluding tickets"
  worker_2day: "CNY 800-1200 excluding tickets"
```

## Writing rules

- Keep factual claims easy to verify.
- Mention whether costs exclude ticket prices.
- Use clear budget and midrange recommendations so persona-specific generation can choose the right content.
- Avoid affiliate links unless the project explicitly adds an affiliate policy.
