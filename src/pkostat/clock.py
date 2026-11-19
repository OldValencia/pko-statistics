"""Local time: every timestamp in the database is Europe/Warsaw wall-clock time."""

from datetime import datetime
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")


def to_local_iso(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("naive datetime: its timezone is unknown")
    return moment.astimezone(WARSAW).replace(tzinfo=None).isoformat(timespec="seconds")


def now_local_iso() -> str:
    return to_local_iso(datetime.now(WARSAW))
