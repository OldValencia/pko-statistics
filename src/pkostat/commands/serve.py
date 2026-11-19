"""`serve` command (also what plain `pkostat` runs): the local admin website."""

import argparse
import threading
import webbrowser

import uvicorn

from pkostat.backup import backup_if_due
from pkostat.config import load_settings
from pkostat.home import open_database
from pkostat.web.app import create_app
from pkostat.web.guard import local_hosts

DEFAULT_PORT = 8765


def cmd_serve(args: argparse.Namespace) -> int:
    settings = load_settings()
    open_database(settings).close()  # fail here, not on the first page load, if `init` never ran
    made = backup_if_due(settings)
    if made:
        print(f"Daily backup: {made}")
    app = create_app(settings, local_hosts(args.port))
    url = f"http://127.0.0.1:{args.port}/"
    print(f"PkoStat: {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, [url]).start()
    # 127.0.0.1 only: the app is for this PC; the published report is a separate static file.
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0
