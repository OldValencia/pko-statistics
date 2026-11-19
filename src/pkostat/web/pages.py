"""Building the admin page: the report for one user plus what the admin pages need."""

import sqlite3
from dataclasses import asdict

from pkostat.backup import list_backups
from pkostat.categorize.config import CategoryConfig, CategoryKind
from pkostat.config import Settings
from pkostat.db.budgets import get_budget
from pkostat.db.categories import list_rules
from pkostat.db.notifications import notification_counts_by_user
from pkostat.db.statements import list_imports
from pkostat.db.suggestions import list_suggestions
from pkostat.db.transactions import category_usage, status_counts, unparsed_notifications
from pkostat.db.users import User, list_users
from pkostat.publish.service import last_publish
from pkostat.publish.sharing import share_link
from pkostat.report.render import render_report
from pkostat.report_service import report_data_for
from pkostat.web.context import category_blockers


def admin_page(
    conn: sqlite3.Connection, settings: Settings, config: CategoryConfig, user: User | None
) -> str:
    data = report_data_for(conn, settings, user)
    admin = _admin_payload(conn, settings, config, list_users(conn), user)
    return render_report(data, "admin", admin=admin)


def _admin_payload(
    conn: sqlite3.Connection,
    settings: Settings,
    config: CategoryConfig,
    users: list[User],
    user: User | None,
) -> dict[str, object]:
    notifications = notification_counts_by_user(conn)
    usage = category_usage(conn)
    rules = list_rules(conn)
    return {
        "current_user": user.name if user else None,
        "users": [
            {
                "name": u.name,
                "label": u.label,
                "display_name": u.display_name,
                "token": u.token,
                "notifications": notifications.get(u.id, 0),
                "share_link": share_link(settings, u),
                "shared": bool(u.share_id),
            }
            for u in users
        ],
        "kinds": [k.value for k in CategoryKind],
        "categories": [
            {
                "name": c.name,
                "label": c.display,
                "kind": c.kind.value,
                "description": c.description,
                "month_shift_from_day": c.month_shift_from_day,
                "transactions": usage.get(c.name, 0),
                "blockers": category_blockers(conn, config, c.name),
            }
            for c in config.categories.values()
        ],
        "rules": [
            {"merchant": key, "category": rule.category, "source": rule.source}
            for key, rule in rules
        ],
        "imports": [asdict(i) for i in list_imports(conn)],
        "statuses": status_counts(conn),
        "unparsed": unparsed_notifications(conn),
        "supabase": bool(settings.supabase_url and settings.supabase_secret_key),
        "llm_model": settings.ollama_model,
        "budget": _budget(conn, user),
        "alternatives": {
            rule.key: {"main": rule.category, "alt": rule.alternative}
            for rule in config.merchant_rules
            if rule.key and rule.category and rule.alternative
        },
        "suggestions": {
            key: {"category": s.category, "confidence": s.confidence}
            for key, s in list_suggestions(conn).items()
        },
        "backups": [
            {
                "name": b.path.name,
                "created": b.created.isoformat(timespec="minutes"),
                "size": b.size,
            }
            for b in list_backups(settings)[:10]
        ],
        "backups_dir": str(settings.backups_dir),
        "publish": {
            "configured": bool(settings.publish_remote),
            "published_at": last_publish(settings).get("published_at"),
        },
    }


def _budget(conn: sqlite3.Connection, user: User | None) -> dict[str, object]:
    plan = get_budget(conn, user.id) if user else None
    return {"goal": plan.goal if plan else None, "limits": plan.limits if plan else {}}
