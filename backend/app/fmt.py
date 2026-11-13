"""Number formatting shared by templates: Indian grouping, true minus sign, one abbreviation style."""
MINUS = "−"
RUPEE = "₹"


def signed_pct(x: float | None, digits: int = 1) -> str:
    if x is None:
        return "n/a"
    return ("+" if x >= 0 else MINUS) + f"{abs(x):.{digits}f}%"


def pts(x: float | None) -> str:
    if x is None:
        return "n/a"
    return ("+" if x >= 0 else MINUS) + f"{abs(x):.1f} pts"


def indian_group(n: float) -> str:
    s = str(int(round(abs(n))))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


def rupees(x: float | None, signed: bool = False) -> str:
    """Abbreviated rupees: 52.1k, 4.2 lakh, 1.02 cr."""
    if x is None:
        return "n/a"
    a = abs(x)
    if a >= 1e7:
        body = f"{a / 1e7:.2f} cr"
    elif a >= 1e5:
        body = f"{a / 1e5:.1f} lakh"
    elif a >= 1e3:
        body = f"{a / 1e3:.1f}k"
    else:
        body = f"{a:.0f}"
    sign = ("+" if x >= 0 else MINUS) if signed else (MINUS if x < 0 else "")
    return f"{sign}{RUPEE}{body}"


def crore(x: float | None) -> str:
    """An amount already in Rs crore -> 'Rs 1,234 cr'."""
    if x is None:
        return "n/a"
    sign = MINUS if x < 0 else ""
    if abs(x) >= 100:
        return f"{sign}{RUPEE}{indian_group(x)} cr"
    return f"{sign}{RUPEE}{abs(x):.1f} cr"


def pct_change(cur: float | None, prev: float | None) -> float | None:
    """% change that stays meaningful when the base is negative (a loss shrinking is +)."""
    if cur is None or prev is None or prev == 0:
        return None
    return (cur - prev) / abs(prev) * 100
