"""`categorize` command: the local LLM suggests categories; the owner confirms them in the app."""

import argparse
from contextlib import closing

from pkostat.categorize.config import load_category_config
from pkostat.config import load_settings
from pkostat.home import open_database
from pkostat.llm.merchants import suggest_categories
from pkostat.llm.ollama import OllamaClient


def cmd_categorize(args: argparse.Namespace) -> int:
    settings = load_settings()
    config = load_category_config(settings.home)
    with (
        closing(open_database(settings)) as conn,
        OllamaClient(settings.ollama_url, settings.ollama_model) as model,
    ):
        result = suggest_categories(conn, model, config, args.limit)
    print(
        f"Asked about {result.asked} merchants: {result.confident} confident suggestions, "
        f"{result.unsure} unsure. Confirm them on the app's Uncategorised page."
    )
    return 0
