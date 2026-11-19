"""'Key: value' lines of IKO notifications, including values continued on the next line."""

import re


def parse_fields(lines: list[str], keys: tuple[str, ...]) -> dict[str, str]:
    """Collect known keys. A non-empty line that starts no known key continues the previous
    value (IKO wraps long titles); a blank line ends it."""
    pattern = re.compile(
        r"^(?P<key>" + "|".join(re.escape(key) for key in keys) + r"):\s*(?P<value>.*)$"
    )
    fields: dict[str, str] = {}
    current: str | None = None
    for raw in lines:
        line = raw.strip()
        if not line:
            current = None
            continue
        match = pattern.match(line)
        if match is not None:
            current = match["key"]
            fields[current] = match["value"].strip()
        elif current is not None:
            fields[current] = f"{fields[current]} {line}".strip()
    return fields


def without_final_period(value: str) -> str:
    return value[:-1].rstrip() if value.endswith(".") else value


def squash_spaces(value: str) -> str:
    return " ".join(value.split())
