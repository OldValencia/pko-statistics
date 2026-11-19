"""`report` command: build the read-only report HTML for one user."""

import argparse
import webbrowser
from contextlib import closing
from pathlib import Path

from pkostat.config import load_settings
from pkostat.home import open_database
from pkostat.report.render import render_report
from pkostat.report_service import report_data_for
from pkostat.users import get_user


def cmd_report(args: argparse.Namespace) -> int:
    settings = load_settings()
    with closing(open_database(settings)) as conn:
        user = get_user(conn, args.user)
        data = report_data_for(conn, settings, user)
    out = Path(args.out) if args.out else settings.reports_dir / user.name / "report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(data, "user"), encoding="utf-8")
    print(f"Report: {out} ({len(data.months)} months, {len(data.transactions)} transactions)")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0
