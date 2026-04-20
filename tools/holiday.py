from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from tools.base import BaseTool, ToolInput, ToolOutput

HOLIDAYS: dict[int, list[tuple[str, date, date]]] = {
    2025: [
        ("New Year", date(2025, 1, 1), date(2025, 1, 1)),
        ("Spring Festival", date(2025, 1, 28), date(2025, 2, 4)),
        ("Qingming", date(2025, 4, 4), date(2025, 4, 6)),
        ("Labor Day", date(2025, 5, 1), date(2025, 5, 5)),
        ("Dragon Boat", date(2025, 5, 31), date(2025, 6, 2)),
        ("National Day", date(2025, 10, 1), date(2025, 10, 8)),
    ],
    2026: [
        ("New Year", date(2026, 1, 1), date(2026, 1, 3)),
        ("Spring Festival", date(2026, 2, 16), date(2026, 2, 22)),
        ("Qingming", date(2026, 4, 4), date(2026, 4, 6)),
        ("Labor Day", date(2026, 5, 1), date(2026, 5, 5)),
        ("Dragon Boat", date(2026, 6, 19), date(2026, 6, 21)),
        ("National Day", date(2026, 10, 1), date(2026, 10, 7)),
    ],
    2027: [
        ("New Year", date(2027, 1, 1), date(2027, 1, 3)),
        ("Spring Festival", date(2027, 2, 5), date(2027, 2, 11)),
        ("Qingming", date(2027, 4, 3), date(2027, 4, 5)),
        ("Labor Day", date(2027, 5, 1), date(2027, 5, 5)),
        ("Dragon Boat", date(2027, 6, 9), date(2027, 6, 11)),
        ("National Day", date(2027, 10, 1), date(2027, 10, 7)),
    ],
}


class HolidayInput(ToolInput):
    year: int
    max_leave_days: int = 3


class HolidayTool(BaseTool):
    name = "holiday_calendar"
    description = "Return China public holidays and simple leave-bridging plans."
    input_model = HolidayInput

    async def execute(self, input: ToolInput) -> ToolOutput:
        params = HolidayInput.model_validate(input)
        holidays = HOLIDAYS.get(params.year, [])
        data = {
            "holidays": [
                {"name": name, "start": start.isoformat(), "end": end.isoformat()}
                for name, start, end in holidays
            ],
            "bridge_plans": self.bridge_plans(params.year, params.max_leave_days),
        }
        return ToolOutput(success=True, data=data)

    def bridge_plans(self, year: int, max_leave_days: int) -> list[dict[str, Any]]:
        plans: list[dict[str, Any]] = []
        for name, start, end in HOLIDAYS.get(year, []):
            leave_start = start - timedelta(days=max_leave_days)
            leave_end = start - timedelta(days=1)
            total_days = (end - leave_start).days + 1
            plans.append(
                {
                    "holiday": name,
                    "leave_days": max_leave_days,
                    "leave_start": leave_start.isoformat(),
                    "leave_end": leave_end.isoformat(),
                    "trip_start": leave_start.isoformat(),
                    "trip_end": end.isoformat(),
                    "total_trip_days": total_days,
                }
            )
        return plans
