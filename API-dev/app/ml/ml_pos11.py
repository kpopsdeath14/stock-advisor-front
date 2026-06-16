"""
Логика рекомендаций — многофакторная APT + оптимизация портфеля.

Факторы: IMOEX, RUB/USD, Brent.
Безрисковая ставка: RUONIA (ЦБ РФ).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from app.config import settings
from app.ml import ck

_STOCKS = ["AFLT.ME", "SBER.ME", "RUAL.ME", "LKOH.ME", "NMTP.ME"]


def _load_factors() -> pd.DataFrame:
    path = Path(settings.data_dir) / "factors.csv"
    if not path.exists():
        raise FileNotFoundError("factors.csv не найден — перезапустите бэкенд.")
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index = ck.normalize_date_index(df.index)
    df = df[["IMOEX", "RUB_USD", "BRENT"]].dropna()
    returns = df.pct_change().dropna().clip(lower=-0.2, upper=0.2)
    return returns


def _load_ruonia() -> pd.Series:
    path = Path(settings.data_dir) / "ruonia.csv"
    if not path.exists():
        raise FileNotFoundError("ruonia.csv не найден — перезапустите бэкенд.")
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index = ck.normalize_date_index(df.index)
    series = df.iloc[:, 0].dropna()
    # cbrapi возвращает ставку в процентах (например, 7.5), переводим в доли
    if series.mean() > 1:
        series = series / 100
    return series


def _load_stock_returns(csv_path: str) -> pd.Series:
    """Загружает CSV сохранённый main.py и возвращает дневные доходности."""
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = ck.normalize_date_index(df.index)
    # Ищем колонку Close (приоритет — Adj Close)
    close_col = next(
        (c for c in df.columns if c.lower() == "adj close"), None
    ) or next(
        (c for c in df.columns if c.lower() == "close"), None
    )
    if close_col is None:
        raise ValueError(f"Нет колонки Close в {csv_path}")
    closes = pd.to_numeric(df[close_col], errors="coerce")
    returns = closes.pct_change().dropna().clip(-0.2, 0.2)
    return returns


def _get_apt_expected_return(
    csv_path: str, ruonia: pd.Series, factors: pd.DataFrame
) -> float:
    """
    Аналог ck.get_apt_expected_return, но использует наш формат CSV (1 строка заголовка).
    ruonia — годовая ставка в долях (например 0.075 для 7.5%).
    """
    stock_returns = _load_stock_returns(csv_path)

    # Конвертируем годовую RUONIA в дневную — как делает ck.get_apt_expected_return
    rf_daily_pct = (1 + ruonia) ** (1 / 252) - 1

    model, metrics = ck.regress_stock_on_factors(stock_returns, factors, rf_daily_pct)

    rf_mean_daily = float(rf_daily_pct.mean())
    rf_aligned = rf_daily_pct.reindex(factors.index).ffill()
    factor_premiums = [
        float((factors["IMOEX"] - rf_aligned).mean()),
        float(factors["RUB_USD"].mean()),
        float(factors["BRENT"].mean()),
    ]
    betas = list(metrics["coefficients"].values())

    return ck.apt_expected_return(rf_mean_daily, betas, factor_premiums)


def get_portfolio_recommendation(A: float) -> dict:
    """
    Запускает многофакторный APT + оптимизацию портфеля для всех акций.
    A — коэффициент неприятия риска (1 = агрессивный, 9 = консервативный).
    """
    factors = _load_factors()
    ruonia  = _load_ruonia()

    rf_daily = (1 + ruonia) ** (1 / 252) - 1
    rf_mean  = float(rf_daily.mean())

    data_dir = Path(settings.data_dir)
    all_returns: dict[str, pd.Series] = {}
    exp_returns_dict: dict[str, float] = {}

    for ticker in _STOCKS:
        csv_path = data_dir / f"{ticker}.csv"
        if not csv_path.exists():
            continue
        try:
            all_returns[ticker] = _load_stock_returns(str(csv_path))
            exp_ret = _get_apt_expected_return(str(csv_path), ruonia, factors)
            exp_returns_dict[ticker] = float(exp_ret)
        except Exception as e:
            print(f"Warning {ticker}: {e}")

    if not exp_returns_dict:
        raise ValueError("Нет данных ни по одной акции.")

    tickers     = list(exp_returns_dict.keys())
    returns_df  = pd.DataFrame({t: all_returns[t] for t in tickers}).dropna()
    exp_returns = np.array([exp_returns_dict[t] for t in tickers])
    cov_matrix  = ck.get_cov_matrix(returns_df)

    portfolio = ck.optimal_complete_portfolio(exp_returns, cov_matrix, rf_mean, A=A)

    risky_weights = portfolio["risky_weights"]
    signals = [
        "buy"  if w > 0.15 else
        "hold" if w > 0.02 else
        "sell"
        for w in risky_weights
    ]

    vol_per_stock = [
        float(returns_df[t].std()) * np.sqrt(252)
        for t in tickers
    ]

    return {
        "tickers":           tickers,
        "risky_weights":     risky_weights.tolist(),
        "risk_free_weight":  float(portfolio["risk_free_weight"]),
        "rf_annual":         round(float(ruonia.mean()), 4),
        "exp_returns":       [round(v * 252, 4) for v in exp_returns.tolist()],
        "volatilities":      vol_per_stock,
        "portfolio_return":  float(portfolio["expected_return"]) * 252,
        "portfolio_vol":     float(portfolio["volatility"]) * np.sqrt(252),
        "sharpe_ratio":      float(portfolio["sharpe_ratio"]),
        "signals":           signals,
        "A":                 A,
    }


def get_recommendation_core(stock_ticker: str, A: float, beta, risk_free_rate: float):
    """Обратная совместимость: возвращает результат для одной акции."""
    result = get_portfolio_recommendation(A)
    tickers = result["tickers"]
    if stock_ticker not in tickers:
        raise ValueError(f"Нет данных для {stock_ticker}")
    idx = tickers.index(stock_ticker)
    w   = result["risky_weights"][idx]
    signal_ru = {"buy": "купить", "hold": "держать", "sell": "продать"}[result["signals"][idx]]
    return (
        result["exp_returns"][idx],
        result["volatilities"][idx],
        w,
        signal_ru,
    )
