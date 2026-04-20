from __future__ import annotations

import json
from pathlib import Path

from rag.knowledge_base import KnowledgeBase

VISA_POLICY_PATH = Path("data/visa_policies.json")

DESTINATION_FACTS: dict[str, dict[str, str]] = {
    "Bangkok": {
        "currency": "Thai Baht (THB), rough planning rate: 1 CNY ~= 5 THB.",
        "timezone": "UTC+7, one hour behind China.",
        "season": "November to February is cooler and drier; April to October can be hot or wet.",
        "language": "Thai is official; English is common in tourist areas.",
        "safety": (
            "Use licensed taxis or ride-hailing, keep valuables close in markets, "
            "and verify temple dress codes."
        ),
    },
    "Chiang Mai": {
        "currency": "Thai Baht (THB), rough planning rate: 1 CNY ~= 5 THB.",
        "timezone": "UTC+7, one hour behind China.",
        "season": (
            "November to February is pleasant; March can have haze, and rainy "
            "season brings short showers."
        ),
        "language": "Thai is official; English is usable around old town and tour areas.",
        "safety": "Check scooter insurance carefully and avoid mountain roads during heavy rain.",
    },
    "Phuket": {
        "currency": "Thai Baht (THB), rough planning rate: 1 CNY ~= 5 THB.",
        "timezone": "UTC+7, one hour behind China.",
        "season": "November to April is best for beaches; May to October has stronger waves.",
        "language": "Thai is official; English is common in resort zones.",
        "safety": "Respect beach red flags and book boats through licensed operators.",
    },
    "Tokyo": {
        "currency": "Japanese Yen (JPY), rough planning rate: 1 CNY ~= 20 JPY.",
        "timezone": "UTC+9, one hour ahead of China.",
        "season": "March to May and October to November are comfortable; summer is humid.",
        "language": "Japanese is official; English signs are common on transit.",
        "safety": "Tokyo is generally safe; keep train etiquette and prepare cash for small shops.",
    },
    "Osaka": {
        "currency": "Japanese Yen (JPY), rough planning rate: 1 CNY ~= 20 JPY.",
        "timezone": "UTC+9, one hour ahead of China.",
        "season": "Spring and autumn are best; summer can be hot and crowded.",
        "language": "Japanese is official; English signs are common on major routes.",
        "safety": "Mind last train times and keep restaurant bookings for popular neighborhoods.",
    },
    "Seoul": {
        "currency": "South Korean Won (KRW), rough planning rate: 1 CNY ~= 190 KRW.",
        "timezone": "UTC+9, one hour ahead of China.",
        "season": "April to June and September to November are comfortable.",
        "language": "Korean is official; English works in airports and major shopping areas.",
        "safety": (
            "Use official taxi apps late at night and carry passport information "
            "for tax refund."
        ),
    },
    "Jeju": {
        "currency": "South Korean Won (KRW), rough planning rate: 1 CNY ~= 190 KRW.",
        "timezone": "UTC+9, one hour ahead of China.",
        "season": "April to June and September to October are good for outdoor routes.",
        "language": "Korean is official; English is less common outside tourist spots.",
        "safety": "Weather changes quickly on Hallasan; check ferry and flight disruption alerts.",
    },
    "Singapore": {
        "currency": "Singapore Dollar (SGD), rough planning rate: 1 SGD ~= 5.3 CNY.",
        "timezone": "UTC+8, same as China.",
        "season": "Year-round warm; rain is possible in any month.",
        "language": "English, Mandarin, Malay, and Tamil are official languages.",
        "safety": (
            "Follow strict local rules on littering, smoking zones, and public "
            "transport behavior."
        ),
    },
    "Kuala Lumpur": {
        "currency": "Malaysian Ringgit (MYR), rough planning rate: 1 MYR ~= 1.5 CNY.",
        "timezone": "UTC+8, same as China.",
        "season": "May to July is relatively drier; short tropical rain is common.",
        "language": "Malay is official; English and Mandarin are widely used in travel areas.",
        "safety": "Use ride-hailing at night and watch bags in crowded transit stations.",
    },
    "Penang": {
        "currency": "Malaysian Ringgit (MYR), rough planning rate: 1 MYR ~= 1.5 CNY.",
        "timezone": "UTC+8, same as China.",
        "season": "December to March is often drier; afternoons can be hot.",
        "language": "Malay is official; English, Mandarin, and Hokkien are common.",
        "safety": "Hydrate during street-food walks and use sun protection in George Town.",
    },
    "Bali": {
        "currency": "Indonesian Rupiah (IDR), rough planning rate: 1 CNY ~= 2200 IDR.",
        "timezone": "UTC+8, same as China.",
        "season": "April to October is drier; November to March is rainy season.",
        "language": "Indonesian is official; English is common in tourism areas.",
        "safety": (
            "Check ocean conditions, avoid unlicensed money changers, and confirm "
            "volcano alerts."
        ),
    },
    "Manila": {
        "currency": "Philippine Peso (PHP), rough planning rate: 1 CNY ~= 8 PHP.",
        "timezone": "UTC+8, same as China.",
        "season": "December to February is cooler; June to November can bring typhoons.",
        "language": "Filipino and English are official.",
        "safety": "Use registered taxis or ride-hailing and monitor weather during typhoon season.",
    },
    "Ho Chi Minh City": {
        "currency": "Vietnamese Dong (VND), rough planning rate: 1 CNY ~= 3500 VND.",
        "timezone": "UTC+7, one hour behind China.",
        "season": "December to April is drier; May to November has more rain.",
        "language": "Vietnamese is official; English is common in tourist districts.",
        "safety": "Watch motorbike traffic and keep phones secure near roads.",
    },
    "Da Nang": {
        "currency": "Vietnamese Dong (VND), rough planning rate: 1 CNY ~= 3500 VND.",
        "timezone": "UTC+7, one hour behind China.",
        "season": "February to May is comfortable; autumn can bring storms.",
        "language": "Vietnamese is official; English is usable in beach and hotel areas.",
        "safety": "Check weather before Ba Na Hills or island trips.",
    },
    "Hong Kong": {
        "currency": "Hong Kong Dollar (HKD), rough planning rate: 1 HKD ~= 0.9 CNY.",
        "timezone": "UTC+8, same as mainland China.",
        "season": "October to December is comfortable; summer is humid and can have typhoons.",
        "language": "Cantonese and English are official; Mandarin is widely understood.",
        "safety": "Use Octopus card for transit and monitor typhoon signal alerts.",
    },
    "Macau": {
        "currency": "Macanese Pataca (MOP), HKD is also widely accepted.",
        "timezone": "UTC+8, same as mainland China.",
        "season": "October to December is comfortable; summer is humid.",
        "language": "Chinese and Portuguese are official; Cantonese is common.",
        "safety": "Plan border crossing time and check hotel shuttle schedules.",
    },
    "Taipei": {
        "currency": "New Taiwan Dollar (TWD), rough planning rate: 1 CNY ~= 4.4 TWD.",
        "timezone": "UTC+8, same as mainland China.",
        "season": "October to April is cooler; summer can bring typhoons.",
        "language": "Mandarin is widely used; Minnan and Hakka are also common.",
        "safety": "Monitor typhoon alerts and use EasyCard for metro and buses.",
    },
    "Chengdu": {
        "currency": "Chinese Yuan (CNY).",
        "timezone": "UTC+8, China standard time.",
        "season": "March to June and September to November are comfortable.",
        "language": "Mandarin is official; Sichuan dialect is common locally.",
        "safety": "Book panda base tickets early and prepare for spicy food if sensitive.",
    },
    "Sanya": {
        "currency": "Chinese Yuan (CNY).",
        "timezone": "UTC+8, China standard time.",
        "season": "November to April is popular for warm beach weather.",
        "language": "Mandarin is official; tourism staff often understand basic English.",
        "safety": "Use sun protection and check beach swimming advisories.",
    },
    "Chongqing": {
        "currency": "Chinese Yuan (CNY).",
        "timezone": "UTC+8, China standard time.",
        "season": "March to May and September to November are easier for walking.",
        "language": "Mandarin is official; Chongqing dialect is common locally.",
        "safety": "Expect steep stairs, crowded viewpoints, and very spicy hotpot.",
    },
}


def seed_knowledge_base(db_path: Path = Path("data/knowledge")) -> int:
    policies = _load_visa_policies()
    knowledge_base = KnowledgeBase(db_path=db_path)
    count = 0
    for policy in policies:
        city = str(policy["city"])
        country = str(policy["country"])
        facts = DESTINATION_FACTS.get(city, {})
        info_text = "\n".join(
            [
                f"Destination: {city}, {country}",
                f"Visa policy: {policy['visa_type']}. {policy['summary']}",
                f"Currency: {facts.get('currency', 'Verify local currency before departure.')}",
                f"Timezone: {facts.get('timezone', 'Verify local time zone before departure.')}",
                "Best travel season: "
                f"{facts.get('season', 'Check recent weather before booking.')}",
                "Local language: "
                f"{facts.get('language', 'Check local language basics before travel.')}",
                "Safety tips: "
                f"{facts.get('safety', 'Verify local safety notices before departure.')}",
            ]
        )
        knowledge_base.add_destination_info(city=city, country=country, info_text=info_text)
        count += 1
    return count


def _load_visa_policies() -> list[dict[str, object]]:
    payload = json.loads(VISA_POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def main() -> None:
    count = seed_knowledge_base()
    print(f"Seeded {count} destination knowledge records")


if __name__ == "__main__":
    main()
