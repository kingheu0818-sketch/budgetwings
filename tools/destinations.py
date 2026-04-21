"""Canonical destination aliases shared across scout and validator."""

from __future__ import annotations

DESTINATION_ALIASES: dict[str, set[str]] = {
    "曼谷": {"曼谷", "Bangkok", "BKK"},
    "清迈": {"清迈", "Chiang Mai", "CNX"},
    "东京": {"东京", "Tokyo", "TYO", "NRT", "HND"},
    "大阪": {"大阪", "Osaka", "KIX"},
    "首尔": {"首尔", "Seoul", "ICN"},
    "海口": {"海口", "Haikou", "HAK"},
    "三亚": {"三亚", "Sanya", "SYX"},
    "成都": {"成都", "Chengdu", "CTU", "TFU"},
    "重庆": {"重庆", "Chongqing", "CKG"},
    "桂林": {"桂林", "Guilin", "KWL"},
    "南宁": {"南宁", "Nanning", "NNG"},
    "贵阳": {"贵阳", "Guiyang", "KWE"},
    "湛江": {"湛江", "Zhanjiang", "ZHA"},
}
