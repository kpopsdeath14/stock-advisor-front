"""
Логика рекомендаций для крипты (APT + доля актива + сигнал).

Отличия от ml_pos11.py:
  - 365 торговых дней в году (крипта торгуется круглосуточно)
  - индекс — BTC-USD как рыночный бенчмарк
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from app.config import settings
from app.ml import ck

_TRADING_DAYS = 365


def _index_file() -> str:
    data_dir = Path(settings.data_dir)
    for name in ("BTC-USD.csv", "btc-usd.csv", "crypto_index.csv"):
        path = data_dir / name
        if path.is_file():
            return str(path)
    raise FileNotFoundError(
        f"Нет файла крипто-индекса в {settings.data_dir}. Ожидается BTC-USD.csv."
    )


def get_recommendation_core(ticker: str, A: float, beta: float, risk_free_rate: float):
    """
    Ядро модели для крипты: возвращает
    ``(expected_return, volatility_annual, optimal_share, signal_ru)``.
    """
    data_dir = Path(settings.data_dir)
    asset_file = str(data_dir / f"{ticker}.csv")
    index_file = _index_file()

    asset_data = ck.load_stock_data(asset_file)
    index_data = ck.load_index_data(index_file)

    b = float(beta) if beta is not None else ck.calculate_beta(
        asset_data["return"], index_data["return"]
    )

    market_premium_daily = ck.predict_market_premium(index_data)
    market_premium_annual = market_premium_daily * _TRADING_DAYS - risk_free_rate

    expected_return = ck.apt_expected_return(risk_free_rate, b, market_premium_annual)

    vol_daily = asset_data["return"].tail(30).std()
    volatility_annual = float(vol_daily) * np.sqrt(_TRADING_DAYS)

    optimal_share = ck.optimal_allocation(expected_return, risk_free_rate, volatility_annual, A)

    if optimal_share > 0.3:
        signal = "купить"
    elif optimal_share > 0:
        signal = "держать"
    else:
        signal = "продать"

    return expected_return, volatility_annual, optimal_share, signal
