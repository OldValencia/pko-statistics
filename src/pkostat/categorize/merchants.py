"""Merchant keys: one name per merchant however the bank spells it.

'WOLT' / 'Wolt' -> 'WOLT' through a rule. Merchants without a rule get a generic clean-up:
upper case, no URL decoration, no tokens with digits (store numbers, order ids), so
'ZABKA Z8828 K.1' and 'ZABKA Z6410 K.1' agree even without a rule.
"""

import re

from pkostat.categorize.config import MerchantRule
from pkostat.domain import Kind

_URL_PREFIX = re.compile(r"^(https?://)?(www\.)?")
_DOMAIN_SUFFIX = re.compile(r"\.(pl|com|eu|net|org|io)(/.*)?$")
_PUNCTUATION = re.compile(r"[\"'*]")
# Card payments often start with the store number ("3091 DEALZ ..."); rules anchored with ^ must
# still see the name first.
_STORE_NUMBER = re.compile(r"^\d+\s+")


def merchant_rule_for(
    counterparty: str | None, kind: Kind, rules: list[MerchantRule]
) -> MerchantRule | None:
    text = _STORE_NUMBER.sub("", counterparty) if counterparty else counterparty
    return next((rule for rule in rules if rule.applies(kind, text)), None)


def merchant_key(counterparty: str | None, kind: Kind, rules: list[MerchantRule]) -> str | None:
    if not counterparty or not counterparty.strip():
        return None
    rule = merchant_rule_for(counterparty, kind, rules)
    if rule is not None and rule.key:
        return rule.key
    return generic_key(counterparty)


def generic_key(counterparty: str) -> str:
    text = _URL_PREFIX.sub("", counterparty.strip().lower())
    text = _DOMAIN_SUFFIX.sub("", text.rstrip("/"))
    text = _PUNCTUATION.sub(" ", text).upper()
    words = [word for word in text.split() if not any(char.isdigit() for char in word)]
    cleaned = " ".join(words).strip(" .-,")
    return cleaned or " ".join(text.split())
