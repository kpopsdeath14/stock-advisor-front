"""
Вызов модели и приведение ответа к контракту API.
"""

from __future__ import annotations

from typing import Any

from app.ml.ml_pos11 import get_recommendation_core

_SIGNAL_TO_ACTION = {"купить": "buy", "держать": "hold", "продать": "sell"}


def _risk_aversion_from_tolerance(risk_tolerance: str | None) -> float:
    if risk_tolerance == "conservative":
        return 6.0
    if risk_tolerance == "aggressive":
        return 2.0
    return 4.0


def get_recommendation(
    ticker: str,
    *,
    risk_tolerance: str | None = None,
    investment_horizon_months: int | None = None,
    risk_free_rate_annual: float | None = None,
    beta: float | None = None,
    risk_aversion_a: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Обёртка над ``get_recommendation_core``: параметры APT и JSON для фронта.

    CSV данные: ``data/{ticker}.csv`` и файл индекса ``data/index.csv`` (или SPY.csv).
    """
    _ = extra
    sym = ticker.strip().upper()
    rf = risk_free_rate_annual if risk_free_rate_annual is not None else 0.04
    A = risk_aversion_a if risk_aversion_a is not None else _risk_aversion_from_tolerance(risk_tolerance)

    # Если beta нет, она посчитается ниже в ml_pos11.py
    expected_return, volatility, optimal_share, signal_ru = get_recommendation_core(sym, A, beta, rf)
    action = _SIGNAL_TO_ACTION.get(signal_ru, "hold")

    summary = (
        f"APT (годовые оценки): ожидаемая доходность {expected_return:.2%}, "
        f"волатильность ~{volatility:.2%}, оптимальная доля актива {optimal_share:.2f}. "
        f"Сигнал: {signal_ru}."
    )

    return {
        "ticker": sym,
        "action": action,
        "confidence": float(min(1.0, max(0.0, optimal_share))),
        "summary": summary,
        "factors": [
            f"beta={beta:.4f}" if beta is not None else "beta=auto",
            f"A={A:.4f}",
            f"risk_free_annual={rf:.4f}",
            f"risk_tolerance={risk_tolerance or 'default'}",
            f"horizon_months={investment_horizon_months or 'n/a'}",
        ],
        "raw": {
            "expected_return_annual": float(expected_return),
            "volatility_annual": float(volatility),
            "optimal_share": float(optimal_share),
            "signal_ru": signal_ru,
        },
    }
