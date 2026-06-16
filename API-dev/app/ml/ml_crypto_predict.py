"""
Предсказание цены и рекомендация по крипто-монете на заданную дату.

Логика:
  - данные берём с Bybit (pybit) за период с 2022-01-01 до cutoff_date
  - cutoff_date = min(target_date, сегодня)
    → если target_date в прошлом, модель видит только то, что было доступно тогда
    → если target_date в будущем, модель обучается на всех текущих данных
  - предсказание цены = last_close × (1 + predicted_daily_return) ^ days_ahead
  - в качестве рыночного бенчмарка используется BTC
  - APT-формула и optimal_allocation — те же что в ml_pos11.py
"""

from __future__ import annotations

from datetime import date

import numpy as np

from app.ml import ck
from app.ml.bybit_data import SUPPORTED_COINS, fetch_coin

_TRADING_DAYS = 365
_RISK_TOLERANCE_TO_A = {"conservative": 6.0, "moderate": 4.0, "aggressive": 2.0}


def _predict_next_return(df: "pd.DataFrame") -> float:  # noqa: F821
    """Обёртка над ck.predict_stock_return — принимает df с колонкой 'return'."""
    # ck ожидает df с колонкой "return"; наш df её имеет
    return float(ck.predict_stock_return(df))


def predict(
    coin: str,
    target_date: date,
    risk_tolerance: str = "moderate",
    risk_free_rate: float = 0.04,
    risk_aversion_a: float | None = None,
) -> dict:
    """
    Возвращает предсказание для монеты на target_date.

    Параметры
    ---------
    coin            : BTC | ETH | SOL | XRP | DOGE | HYPE
    target_date     : дата предсказания (прошлое или будущее)
    risk_tolerance  : conservative | moderate | aggressive
    risk_free_rate  : годовая безрисковая ставка (дробь, например 0.04)
    risk_aversion_a : переопределяет risk_tolerance если задан
    """
    coin = coin.upper()
    if coin not in SUPPORTED_COINS:
        raise ValueError(f"Неизвестная монета '{coin}'. Доступны: {', '.join(SUPPORTED_COINS)}")

    A = risk_aversion_a or _RISK_TOLERANCE_TO_A.get(risk_tolerance, 4.0)
    cutoff = min(target_date, date.today())

    # ── загружаем данные монеты и BTC-индекса ──────────────────────────────────
    asset_df = fetch_coin(coin, cutoff)
    btc_df   = fetch_coin("BTC", cutoff)

    if len(asset_df) < 30:
        raise ValueError(f"Недостаточно данных для {coin} (меньше 30 дней)")

    # ── бета относительно BTC ──────────────────────────────────────────────────
    if coin == "BTC":
        beta = 1.0
    else:
        beta = ck.calculate_beta(asset_df["return"], btc_df["return"])

    # ── рыночная премия через ML на BTC ───────────────────────────────────────
    market_premium_daily  = ck.predict_market_premium(btc_df)
    market_premium_annual = market_premium_daily * _TRADING_DAYS - risk_free_rate

    # ── ожидаемая доходность по APT ────────────────────────────────────────────
    expected_return_annual = ck.apt_expected_return(risk_free_rate, beta, market_premium_annual)

    # ── волатильность (30-дневная → годовая) ───────────────────────────────────
    vol_daily  = float(asset_df["return"].tail(30).std())
    vol_annual = vol_daily * np.sqrt(_TRADING_DAYS)

    # ── оптимальная доля портфеля ─────────────────────────────────────────────
    optimal_share = ck.optimal_allocation(expected_return_annual, risk_free_rate, vol_annual, A)

    # ── предсказание цены ─────────────────────────────────────────────────────
    last_date  = asset_df["Date"].iloc[-1]
    last_close = float(asset_df["Close"].iloc[-1])

    predicted_daily_return = _predict_next_return(asset_df)
    days_ahead = max((target_date - last_date).days, 1)
    predicted_price = last_close * (1 + predicted_daily_return) ** days_ahead

    # ── сигнал ────────────────────────────────────────────────────────────────
    if optimal_share > 0.3:
        signal = "buy"
    elif optimal_share > 0:
        signal = "hold"
    else:
        signal = "sell"

    return {
        "coin":                      coin,
        "symbol":                    SUPPORTED_COINS[coin],
        "target_date":               target_date.isoformat(),
        "data_cutoff_date":          last_date.isoformat(),
        "days_ahead":                days_ahead,
        "last_known_price_usdt":     round(last_close, 4),
        "predicted_price_usdt":      round(predicted_price, 4),
        "predicted_return_pct":      round(predicted_daily_return * days_ahead * 100, 2),
        "expected_return_annual_pct": round(expected_return_annual * 100, 1),
        "volatility_annual_pct":     round(vol_annual * 100, 1),
        "recommended_share_pct":     round(optimal_share * 100, 1),
        "signal":                    signal,
        "beta_vs_btc":               round(beta, 4),
        "risk_tolerance":            risk_tolerance,
    }
