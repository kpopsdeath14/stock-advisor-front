from pathlib import Path

import pandas as pd


# Поддерживаемые имена колонок (после нормализации — lowercase)
_DATE_ALIASES = ("date", "time", "datetime", "timestamp")
_CLOSE_ALIASES = ("close", "adj close", "adj_close", "adjclose", "last")
_OPEN_ALIASES = ("open",)
_HIGH_ALIASES = ("high",)
_LOW_ALIASES = ("low",)
_VOLUME_ALIASES = ("volume", "vol")


def _pick_column(columns: pd.Index, aliases: tuple[str, ...]) -> str | None:
    lower = {c.lower().strip(): c for c in columns}
    for a in aliases:
        if a in lower:
            return lower[a]
    return None


def load_price_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"CSV не найден: {path}")

    df = pd.read_csv(path)
    if df.empty:
        raise ValueError("CSV пустой")

    df.columns = [str(c).strip() for c in df.columns]

    date_col = _pick_column(df.columns, _DATE_ALIASES)
    close_col = _pick_column(df.columns, _CLOSE_ALIASES)
    if not date_col or not close_col:
        raise ValueError(
            "В CSV нужны колонки даты (date/time/...) и цены закрытия (close/adj close/...)"
        )

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df[date_col], errors="coerce").dt.date
    out["close"] = pd.to_numeric(df[close_col], errors="coerce")

    for alias, aliases, name in (
        (_pick_column(df.columns, _OPEN_ALIASES), _OPEN_ALIASES, "open"),
        (_pick_column(df.columns, _HIGH_ALIASES), _HIGH_ALIASES, "high"),
        (_pick_column(df.columns, _LOW_ALIASES), _LOW_ALIASES, "low"),
        (_pick_column(df.columns, _VOLUME_ALIASES), _VOLUME_ALIASES, "volume"),
    ):
        if alias:
            out[name] = pd.to_numeric(df[alias], errors="coerce")

    out = out.dropna(subset=["date", "close"])
    out = out.sort_values("date")
    return out.reset_index(drop=True)
