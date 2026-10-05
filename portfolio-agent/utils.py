"""utils.py - small formatting helpers."""


def fmt_inr(x):
    """Format rupees the Indian way: Rs 4.50 L, Rs 1.25 Cr."""
    if x is None:
        return "-"
    x = float(x)
    if abs(x) >= 1e7:
        return f"Rs {x / 1e7:.2f} Cr"
    if abs(x) >= 1e5:
        return f"Rs {x / 1e5:.2f} L"
    return f"Rs {x:,.0f}"


def pct(x, digits=0):
    return "-" if x is None else f"{x * 100:.{digits}f}%"
