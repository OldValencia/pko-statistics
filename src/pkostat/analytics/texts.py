"""Russian wording helpers for texts built by code."""

MONTH_PREP = ["январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе",
              "сентябре", "октябре", "ноябре", "декабре"]  # fmt: skip
MONTH_NOM = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август",
             "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]  # fmt: skip


def zl(minor: int | float) -> str:
    """Whole złoty with a thin grouping, sign dropped: the sentence says which way it went."""
    return f"{round(abs(minor) / 100):,}".replace(",", "\u00a0") + "\u00a0zł"


def plural(n: int, one: str, few: str, many: str) -> str:
    tail, last = abs(n) % 100, abs(n) % 10
    word = many if 10 < tail < 20 else few if 1 < last < 5 else one if last == 1 else many
    return f"{n} {word}"


def in_month(month: str) -> str:
    return "в " + MONTH_PREP[int(month[5:7]) - 1]


def month_name(month: str) -> str:
    return MONTH_NOM[int(month[5:7]) - 1]
