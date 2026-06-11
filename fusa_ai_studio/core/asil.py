from __future__ import annotations


ASIL_ORDER = ["QM", "A", "B", "C", "D"]


def calculate_asil(severity: int, exposure: int, controllability: int) -> str:
    if severity <= 0:
        return "QM"
    score = severity + exposure + controllability
    if score <= 5:
        return "QM"
    if score == 6:
        return "A"
    if score == 7:
        return "B"
    if score == 8:
        return "C"
    return "D"


def max_asil(*values: str) -> str:
    normalized = [value for value in values if value in ASIL_ORDER]
    if not normalized:
        return "QM"
    return max(normalized, key=ASIL_ORDER.index)
