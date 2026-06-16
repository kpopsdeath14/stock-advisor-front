"""
Отдельный FastAPI-сервер для крипто-рекомендаций.
Запуск: uvicorn crypto_main:app --host 0.0.0.0 --port 4401
"""

import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.ml import ml_crypto, ml_crypto_predict
from app.ml.bybit_data import SUPPORTED_COINS

app = FastAPI(
    title="Crypto Recommendations API",
    description="Рекомендации и предсказания цен по криптовалютам (BTC, ETH, SOL, XRP, DOGE, HYPE).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_RISK_TOLERANCE_TO_A = {"conservative": 6.0, "moderate": 4.0, "aggressive": 2.0}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/coins")
def coins():
    """Список поддерживаемых монет."""
    return {"supported_coins": list(SUPPORTED_COINS.keys())}


# ── Рекомендация (на основе CSV с Bybit-данными) ─────────────────────────────

class RecommendationRequest(BaseModel):
    ticker: str
    risk_tolerance: str = "moderate"   # conservative | moderate | aggressive
    risk_free_rate_annual: float = 0.04
    beta: float | None = None
    risk_aversion_a: float | None = None


@app.post("/recommendation")
def recommendation(req: RecommendationRequest):
    """
    Рекомендация по монете на основе APT-модели.
    Данные берутся из CSV-файлов (data/{TICKER}.csv и data/BTC-USD.csv как индекс).
    """
    A = req.risk_aversion_a or _RISK_TOLERANCE_TO_A.get(req.risk_tolerance, 4.0)
    try:
        exp_ret, vol, share, signal_ru = ml_crypto.get_recommendation_core(
            req.ticker.upper(), A, req.beta, req.risk_free_rate_annual
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    _signal_map = {"купить": "buy", "держать": "hold", "продать": "sell"}
    return {
        "ticker":             req.ticker.upper(),
        "expected_return_pct": round(exp_ret * 100, 1),
        "volatility_pct":     round(vol * 100, 2),
        "recommended_share_pct": round(share * 100, 1),
        "signal":             _signal_map.get(signal_ru, "hold"),
    }


# ── Предсказание цены на дату ─────────────────────────────────────────────────

class PredictRequest(BaseModel):
    coin: str
    target_date: datetime.date
    risk_tolerance: str = "moderate"
    risk_free_rate: float = 0.04
    risk_aversion_a: float | None = None


@app.post("/predict")
def predict(req: PredictRequest):
    """
    Предсказание цены монеты на заданную дату.
    Данные загружаются с Bybit через pybit.

    - target_date в прошлом → модель видит только данные до той даты
    - target_date в будущем → модель обучается на всех доступных данных
    """
    try:
        result = ml_crypto_predict.predict(
            coin=req.coin,
            target_date=req.target_date,
            risk_tolerance=req.risk_tolerance,
            risk_free_rate=req.risk_free_rate,
            risk_aversion_a=req.risk_aversion_a,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return result
