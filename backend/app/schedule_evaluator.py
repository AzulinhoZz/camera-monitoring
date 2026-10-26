import logging
from typing import Optional, List
from datetime import datetime, time
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

logger = logging.getLogger("schedule_evaluator")

SENSITIVITY_PRESETS = {
    "low": {"min_area": 3000, "threshold": 35, "cooldown_seconds": 10.0},
    "medium": {"min_area": 1500, "threshold": 25, "cooldown_seconds": 5.0},
    "high": {"min_area": 500, "threshold": 15, "cooldown_seconds": 2.0},
}

DAY_MAP = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun"
}


def parse_time_str(time_str: str) -> time:
    """Parses time string HH:MM or HH:MM:SS into datetime.time object."""
    if not time_str:
        return time(0, 0)
    parts = time_str.strip().split(":")
    h = int(parts[0]) if len(parts) > 0 else 0
    m = int(parts[1]) if len(parts) > 1 else 0
    s = int(parts[2]) if len(parts) > 2 else 0
    return time(h, m, s)


def is_schedule_active(
    schedule_type: str = "24/7",
    schedule_days: Optional[List[str]] = None,
    start_time_str: str = "00:00:00",
    end_time_str: str = "23:59:59",
    tz_name: str = "America/Mexico_City",
    dt_override: Optional[datetime] = None
) -> bool:
    if schedule_type == "24/7":
        return True

    if not schedule_days:
        schedule_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    try:
        tz = ZoneInfo(tz_name)
    except Exception as e:
        logger.warning(f"Invalid timezone '{tz_name}', falling back to America/Mexico_City: {e}")
        tz = ZoneInfo("America/Mexico_City")

    # Get current time in specified camera IANA timezone
    now_local = dt_override if dt_override is not None else datetime.now(tz)
    if now_local.tzinfo is None:
        now_local = now_local.replace(tzinfo=tz)

    current_day = DAY_MAP.get(now_local.weekday(), "mon")
    if current_day not in [d.lower() for d in schedule_days]:
        return False

    current_time = now_local.time()
    start_t = parse_time_str(start_time_str)
    end_t = parse_time_str(end_time_str)

    if start_t <= end_t:
        # Standard day time range (e.g. 08:00 to 18:00)
        return start_t <= current_time <= end_t
    else:
        # Overnight range crossing midnight (e.g. 22:00 to 06:00)
        return current_time >= start_t or current_time <= end_t
