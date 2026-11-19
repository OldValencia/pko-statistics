# PkoStat — General Idea

## Why

Money leaks away unnoticed: food delivery, taxis, convenience stores, small online purchases. The
banking app shows a list of transactions but doesn't answer the questions that matter:

- how much do I actually spend, and on what — by category and by month;
- what is necessary, and what is habit and laziness;
- what exactly should I cut, how much will that save per month, and **is it working**.

PkoStat is a personal tool that answers these questions from your own PKO BP data, without sending it
to any cloud other than a short-lived buffer for push notifications.

## Who it's for

One person (the author) and possibly one more. User data is **never mixed**: each has their own token,
transactions, budgets and report. This is not SaaS or a multi-tenant service: no sign-ups, no roles, no
admin web UI.

## How it works (short version)

1. The iPhone catches IKO pushes and sends the text to Supabase (Shortcuts).
2. `pkostat sync` pulls notifications to the PC and deletes them from the cloud.
3. Once a month/quarter — `pkostat import-csv` with an iPKO statement: a complete, exact history that
   fills in missed pushes.
4. Python normalises transactions, reconciles pushes against the statement and computes statistics.
5. A local LLM (Ollama, gpt-oss:20b) assigns unfamiliar merchants to categories and writes insights and
   recommendations **based on already-computed numbers**.
6. The output is a single HTML file with KPIs, charts, "leaks", recommendations and a transaction
   register.

Details — `docs/pko-expenses-architecture.md`.

## What success looks like

- A monthly report is generated with one command, and its numbers match the statement to the grosz.
- Every recommendation is concrete and quantified: "Wolt: 47 orders, 3,120 zł; 10 orders a month would
  save ~2,400 zł", not "try to spend less".
- Progress is visible: is it better than last month, is the limit holding, is the savings rate growing.
- For a user who has set goals (optional) — progress towards the savings goal.

## What we don't do

- No bank APIs, no Open Banking, no paid aggregators.
- No bank data sent to cloud LLMs.
- No public web application: the full app runs locally for the owner only; others get a read-only
  HTML report published at a secret link (a separate, later stage).
- No bookkeeping: no manual transaction entry; cash is tracked only as ATM withdrawals.
- No shared household budget.

## Constraints to keep in mind

- A push is a **hold**, not a final charge, and some transactions produce no push at all. So the CSV
  statement is the source of truth; pushes are interim data until the next statement.
- LLMs get arithmetic wrong and can be inconsistent. The LLM doesn't compute money and doesn't decide
  what is "bad" — that is set in the category config; it explains and suggests.
- After `sync` a notification exists only on the local disk. Without a backup its loss is permanent
  (except by re-importing a CSV).
