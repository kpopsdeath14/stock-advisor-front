"""
Загрузка исторических дневных свечей с Bybit через pybit.
Поддерживаемые монеты: BTC, ETH, SOL, XRP, DOGE, HYPE.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
from pybit.unified_trading import HTTP

_session = HTTP()  # публичный эндпоинт, авторизация не нужна

SUPPORTED_COINS = {
    "BTC":  "BTCUSDT",
    "ETH":  "ETHUSDT",
    "SOL":  "SOLUSDT",
    "XRP":  "XRPUSDT",
    "DOGE": "DOGEUSDT",
    "HYPE": "HYPEUSDT",
}

_DATA_START = "2022-01-01"


def _to_ms(d: date | str) -> int:
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def fetch_ohlcv(symbol: str, start: date | str, end: date | str) -> pd.DataFrame:
    """
    Возвращает дневные OHLCV для symbol (например 'BTCUSDT').
    Автоматически пагинирует — Bybit отдаёт max 1000 свечей за запрос.
    """
    start_ms = _to_ms(start)
    end_ms   = _to_ms(end)

    rows: list[list] = []
    current_end = end_ms

    while current_end > start_ms:
        resp = _session.get_kline(
            category="linear",
            symbol=symbol,
            interval="D",
            start=start_ms,
            end=current_end,
            limit=1000,
        )
        bars = resp.get("result", {}).get("list", [])
        if not bars:
            break
        rows.extend(bars)
        oldest_ts = int(bars[-1][0])
        if oldest_ts <= start_ms:
            break
        current_end = oldest_ts - 86_400_000  # шаг назад на один день

    if not rows:
        raise ValueError(f"Bybit не вернул данные для {symbol}")

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume", "turnover"])
    df["Date"] = pd.to_datetime(df["ts"].astype(int), unit="ms", utc=True).dt.date
    df = df.drop_duplicates("Date").sort_values("Date").reset_index(drop=True)

    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col])

    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                             "close": "Close", "volume": "Volume"})
    df["return"] = df["Close"].pct_change()
    return df[["Date", "Open", "High", "Low", "Close", "Volume", "return"]]


def fetch_coin(coin: str, cutoff: date | None = None) -> pd.DataFrame:
    """
    Удобная обёртка: принимает короткое имя монеты (BTC, ETH …).
    cutoff — включительная правая граница (по умолчанию сегодня).
    """
    symbol = SUPPORTED_COINS.get(coin.upper())
    if not symbol:
        raise ValueError(
            f"Неизвестная монета '{coin}'. Доступны: {', '.join(SUPPORTED_COINS)}"
        )
    end = cutoff or date.today()
    return fetch_ohlcv(symbol, _DATA_START, end)
