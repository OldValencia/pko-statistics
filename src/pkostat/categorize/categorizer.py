"""Category assignment. First match wins:

1. transaction_overrides     a manual fix of one operation;
2. merchant_rules 'manual'   `pkostat category set <merchant> <category>`;
3. title rules               rules.toml [[title]] (salary by 'Wynagrodzenie', …);
4. merchant rules            rules.toml [[merchant]] with a category;
5. defaults                  rules.toml [defaults] by kind (ATM, transfers);
6. merchant_rules 'llm'      the LLM's earlier answers (stage 6);
7. nothing                   uncategorised, waits for the LLM.

Refunds go through the same chain, so a Wolt refund lands in Food delivery and lowers it.
"""

from dataclasses import replace

from pkostat.categorize.config import CategoryConfig
from pkostat.categorize.merchants import merchant_key, merchant_rule_for
from pkostat.db.categories import StoredRule
from pkostat.domain import Kind, Transaction


class Categorizer:
    def __init__(
        self,
        config: CategoryConfig,
        stored_rules: dict[str, StoredRule],
        overrides: dict[tuple[str, int], str],
    ) -> None:
        self._config = config
        # A stored rule naming a category since removed from categories.toml is ignored.
        self._stored = {
            key: rule for key, rule in stored_rules.items() if rule.category in config.categories
        }
        self._overrides = {
            ref: name for ref, name in overrides.items() if name in config.categories
        }

    def with_merchant_key(self, tx: Transaction) -> Transaction:
        key = merchant_key(tx.counterparty, tx.kind, self._config.merchant_rules)
        return replace(tx, merchant_key=key)

    def inherit_override(self, replaced: Transaction) -> None:
        """A push or hold the statement superseded hands its manual category to the row that
        replaced it: marking a Wolt order as groceries must survive the statement's arrival.
        An override set on the replacing row itself wins."""
        if replaced.matched_csv_row_id is None:
            return
        own = self._overrides.get((replaced.source, replaced.source_id))
        target = ("csv", replaced.matched_csv_row_id)
        if own is not None and target not in self._overrides:
            self._overrides[target] = own

    def with_category(self, tx: Transaction) -> Transaction:
        return replace(tx, category=self.category_for(tx))

    def category_for(self, tx: Transaction) -> str | None:
        override = self._overrides.get((tx.source, tx.source_id))
        if override is not None:
            return override
        stored = self._stored.get(tx.merchant_key) if tx.merchant_key else None
        if stored is not None and stored.source == "manual":
            return stored.category
        title_rule = next(
            (rule for rule in self._config.title_rules if rule.applies(tx.kind, tx.title)), None
        )
        if title_rule is not None:
            return title_rule.category
        merchant_rule = merchant_rule_for(tx.counterparty, tx.kind, self._config.merchant_rules)
        if merchant_rule is not None and merchant_rule.category:
            return merchant_rule.category
        default = self._default_for(tx.kind)
        if default is not None:
            return default
        return stored.category if stored is not None else None

    def _default_for(self, kind: Kind) -> str | None:
        defaults = self._config.defaults
        return {
            Kind.ATM: defaults.atm,
            Kind.TRANSFER_IN: defaults.transfer_in,
            Kind.TRANSFER_OUT: defaults.transfer_out,
        }.get(kind)
