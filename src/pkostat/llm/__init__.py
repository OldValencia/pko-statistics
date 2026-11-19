"""The local LLM (Ollama): sorting unknown merchants and writing the month's summary.

It never computes money: it receives numbers from `analytics` and returns categories or text,
always through a pydantic schema.
"""
