import sqlite3

from pkostat.domain import Budget


def get_budget(conn: sqlite3.Connection, user_id: int) -> Budget:
    goal = conn.execute("SELECT monthly_saving FROM goals WHERE user_id = ?", (user_id,)).fetchone()
    rows = conn.execute(
        "SELECT category, month_limit FROM budgets WHERE user_id = ?", (user_id,)
    ).fetchall()
    return Budget(
        goal=goal["monthly_saving"] if goal else None,
        limits={row["category"]: row["month_limit"] for row in rows},
    )


def save_budget(conn: sqlite3.Connection, user_id: int, budget: Budget) -> None:
    """Replace the user's whole plan in one go, as the page submits it."""
    conn.execute("DELETE FROM goals WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM budgets WHERE user_id = ?", (user_id,))
    if budget.goal is not None:
        conn.execute(
            "INSERT INTO goals (user_id, monthly_saving) VALUES (?, ?)", (user_id, budget.goal)
        )
    conn.executemany(
        "INSERT INTO budgets (user_id, category, month_limit) VALUES (?, ?, ?)",
        [(user_id, category, limit) for category, limit in budget.limits.items()],
    )
