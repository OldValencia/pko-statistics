"""ReportData for one user, as the CLI, the pipeline and the web app all need it."""

import sqlite3
from datetime import datetime

from pkostat.analytics.model import ReportData
from pkostat.analytics.report_data import build_report_data
from pkostat.categorize.config import load_category_config
from pkostat.clock import WARSAW
from pkostat.config import Settings
from pkostat.db.budgets import get_budget
from pkostat.db.statements import covered_from
from pkostat.db.transactions import list_transactions
from pkostat.db.users import User


def report_data_for(conn: sqlite3.Connection, settings: Settings, user: User | None) -> ReportData:
    first_day = covered_from(conn, user.id) if user else None
    return build_report_data(
        user.label if user else "PkoStat",
        list_transactions(conn, user.id) if user else [],
        load_category_config(settings.home),
        datetime.now(WARSAW).date(),
        start_month=first_day[:7] if first_day else None,
        budget=get_budget(conn, user.id) if user else None,
    )
