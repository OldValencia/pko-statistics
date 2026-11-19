from pkostat.domain import Kind, Source, Status, Transaction
from pkostat.reconcile import reconcile


def _tx(
    source: Source,
    source_id: int,
    day: str,
    amount: int,
    kind: Kind = Kind.CARD,
    counterparty: str | None = None,
) -> Transaction:
    return Transaction(
        user_id=1,
        source=source,
        source_id=source_id,
        occurred_on=day,
        occurred_at=None,
        amount_minor=amount,
        currency="PLN",
        kind=kind,
        counterparty=counterparty,
        merchant_key=counterparty,
        location=None,
        title=None,
        status=Status.SETTLED if source == Source.CSV else Status.PENDING,
    )


def _push(
    source_id: int, day: str, amount: int, kind: Kind = Kind.CARD, merchant: str | None = None
) -> Transaction:
    return _tx(Source.NOTIFICATION, source_id, day, amount, kind, merchant)


def _row(
    source_id: int, day: str, amount: int, kind: Kind = Kind.CARD, merchant: str | None = None
) -> Transaction:
    return _tx(Source.CSV, source_id, day, amount, kind, merchant)


def _statuses(result: list[Transaction]) -> dict[int, tuple[Status, int | None]]:
    return {tx.source_id: (tx.status, tx.matched_csv_row_id) for tx in result}


def test_no_statement_means_all_pending() -> None:
    result = reconcile([_push(1, "2026-11-01", -100)], [], None)

    assert _statuses(result) == {1: (Status.PENDING, None)}


def test_matches_within_window() -> None:
    result = reconcile(
        [_push(1, "2026-11-10", -7021)], [_row(50, "2026-11-12", -7021)], "2026-11-30"
    )

    assert _statuses(result) == {1: (Status.SUPERSEDED, 50)}


def test_outside_window_or_other_amount_does_not_match() -> None:
    pushes = [_push(1, "2026-11-01", -7021), _push(2, "2026-11-10", -7000)]
    rows = [_row(50, "2026-11-10", -7021)]

    result = reconcile(pushes, rows, "2026-11-30")

    assert _statuses(result) == {1: (Status.UNMATCHED, None), 2: (Status.UNMATCHED, None)}


def test_identical_purchases_match_one_to_one() -> None:
    pushes = [_push(1, "2026-11-10", -1200), _push(2, "2026-11-10", -1200)]
    rows = [_row(50, "2026-11-10", -1200)]

    result = reconcile(pushes, rows, "2026-11-30")

    assert _statuses(result) == {1: (Status.SUPERSEDED, 50), 2: (Status.UNMATCHED, None)}


def test_prefers_same_kind_then_closest_day() -> None:
    pushes = [_push(1, "2026-11-10", -1200, Kind.TRANSFER_OUT)]
    rows = [
        _row(50, "2026-11-10", -1200, Kind.CARD),
        _row(51, "2026-11-12", -1200, Kind.TRANSFER_OUT),
        _row(52, "2026-11-11", -1200, Kind.TRANSFER_OUT),
    ]

    result = reconcile(pushes, rows, "2026-11-30")

    assert _statuses(result) == {1: (Status.SUPERSEDED, 52)}


def test_recent_unmatched_push_stays_pending() -> None:
    # Bought on the statement's last days: still a hold ('Blokada'), not exported as settled.
    pushes = [_push(1, "2026-11-10", -500), _push(2, "2026-11-12", -500)]

    result = reconcile(pushes, [], "2026-11-12")

    assert _statuses(result) == {1: (Status.PENDING, None), 2: (Status.PENDING, None)}


def test_push_after_statement_is_pending() -> None:
    result = reconcile([_push(1, "2026-11-20", -500)], [_row(50, "2026-11-20", -500)], "2026-11-12")

    assert _statuses(result) == {1: (Status.PENDING, None)}


def test_adjusted_card_hold_matches_same_merchant() -> None:
    # Real case: Wolt authorised 273,15, the statement hold says 268,33.
    pushes = [_push(1, "2026-11-17", -27315, merchant="WOLT")]
    rows = [_row(50, "2026-11-17", -26833, merchant="WOLT")]

    result = reconcile(pushes, rows, "2026-11-18")

    assert _statuses(result) == {1: (Status.SUPERSEDED, 50)}


def test_similar_needs_same_merchant_close_amount_and_day() -> None:
    pushes = [
        _push(1, "2026-11-17", -27315, merchant="WOLT"),
        _push(2, "2026-11-17", -10000, merchant="WOLT"),
        _push(3, "2026-11-10", -5000, merchant="WOLT"),
        _push(4, "2026-11-17", -5000, Kind.TRANSFER_OUT, merchant="WOLT"),
    ]
    rows = [
        _row(50, "2026-11-17", -26833, merchant="BOLT.EU/O/26111"),  # other merchant
        _row(51, "2026-11-17", -8000, merchant="WOLT"),  # 20 % off
        _row(52, "2026-11-12", -4900, merchant="WOLT"),  # two days apart
        _row(53, "2026-11-17", -4900, Kind.TRANSFER_OUT, merchant="WOLT"),  # not a card
    ]

    result = reconcile(pushes, rows, "2026-11-18")

    assert {i: s for i, (s, _) in _statuses(result).items()} == {
        1: Status.PENDING,
        2: Status.PENDING,
        3: Status.UNMATCHED,
        4: Status.PENDING,
    }


def test_exact_pair_is_not_stolen_by_an_earlier_similar_push() -> None:
    # Push 1 comes first and is only similar to row 51; push 2 is its exact pair.
    pushes = [
        _push(1, "2026-11-17", -5000, merchant="WOLT"),
        _push(2, "2026-11-17", -5200, merchant="WOLT"),
    ]
    rows = [_row(51, "2026-11-17", -5200, merchant="WOLT")]

    result = reconcile(pushes, rows, "2026-11-18")

    assert _statuses(result) == {1: (Status.PENDING, None), 2: (Status.SUPERSEDED, 51)}
