import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import cors_origins_list, settings
from app.price_history import load_price_csv
from app.recommendation_service import get_recommendation
from app.schemas import PriceBar, PriceHistoryResponse, RecommendationRequest, RecommendationResponse

PUBLIC_DIR = Path(__file__).resolve().parent.parent.parent / "public"

_STOCKS = ["AFLT.ME", "SBER.ME", "RUAL.ME", "LKOH.ME", "NMTP.ME"]
_STOCK_NAMES = {
    "AFLT.ME": "Аэрофлот",
    "SBER.ME": "Сбербанк",
    "RUAL.ME": "Русал",
    "LKOH.ME": "Лукойл",
    "NMTP.ME": "НМТП",
}

def _download_data():
    import yfinance as yf
    end = "2022-01-01"
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(exist_ok=True)

    # Факторы: IMOEX, RUB/USD, Brent — по отдельности чтобы не перепутать порядок колонок
    for yf_ticker, col in [("IMOEX.ME", "IMOEX"), ("RUB=X", "RUB_USD"), ("BZ=F", "BRENT")]:
        print(f"Downloading {yf_ticker}...")
        df = yf.download(yf_ticker, start=settings.data_start_date, end=end,
                         auto_adjust=False, progress=False, timeout=30)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if not df.empty:
            close = df[["Close"]].rename(columns={"Close": col})
            factors_path = data_dir / "factors.csv"
            if factors_path.exists():
                existing = pd.read_csv(factors_path, index_col=0, parse_dates=True)
                existing[col] = close[col]
                existing.to_csv(factors_path)
            else:
                close.to_csv(factors_path)
            print(f"Updated factors.csv column '{col}' ({len(df)} rows)")
        else:
            print(f"Warning: no data for {yf_ticker}")

    # RUONIA
    try:
        import cbrapi as cbr
        print("Downloading RUONIA...")
        ruonia = cbr.ruonia.get_ruonia_overnight(settings.data_start_date, end, "D")
        ruonia.to_csv(data_dir / "ruonia.csv")
        print(f"Saved ruonia.csv ({len(ruonia)} rows)")
    except Exception as e:
        print(f"Warning: RUONIA download failed: {e}")

    # Акции
    for ticker in _STOCKS:
        print(f"Downloading {ticker}...")
        df = yf.download(ticker, start=settings.data_start_date, end=end,
                         auto_adjust=False, progress=False, timeout=30)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if not df.empty:
            df.to_csv(data_dir / f"{ticker}.csv")
            print(f"Saved {ticker}.csv ({len(df)} rows)")
        else:
            print(f"Warning: no data for {ticker}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await asyncio.to_thread(_download_data)
    except Exception as e:
        print(f"Data download failed: {e}")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Investment recommendations API",
    version="0.1.0",
)

_origins = cors_origins_list()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials="*" not in _origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def index():
    return FileResponse(PUBLIC_DIR / "index.html")


# ── Портфельная рекомендация по всем акциям ─────────────────────────────────

class PortfolioRequest(BaseModel):
    A: float  # 1, 3 или 9


@app.post("/portfolio-recommendation")
def portfolio_recommendation(req: PortfolioRequest):
    from app.ml.ml_pos11 import get_portfolio_recommendation
    try:
        result = get_portfolio_recommendation(req.A)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    tickers   = result["tickers"]
    weights   = result["risky_weights"]
    signals   = result["signals"]
    exp_rets  = result["exp_returns"]
    vols      = result["volatilities"]

    rows = [
        {
            "ticker":          t,
            "name":            _STOCK_NAMES.get(t, t),
            "expected_return": round(exp_rets[i] * 100, 1),
            "volatility":      round(vols[i] * 100, 1),
            "optimal_share":   round(weights[i] * 100, 1),
            "signal":          signals[i],
        }
        for i, t in enumerate(tickers)
    ]

    rf_share = round(result["risk_free_weight"] * 100, 1)
    rf_return = round(result["rf_annual"] * 100, 1)
    rows.append({
        "ticker":          "ОФЗ",
        "name":            "Облигации федерального займа",
        "expected_return": rf_return,
        "volatility":      0.0,
        "optimal_share":   rf_share,
        "signal":          "hold",
    })

    lines = ["ticker,name,expected_return,volatility,optimal_share,signal"] + [
        f"{r['ticker']},{r['name']},{r['expected_return']},{r['volatility']},{r['optimal_share']},{r['signal']}"
        for r in rows
    ]
    (Path(settings.data_dir) / "portfolio.csv").write_text("\n".join(lines))

    return {"A": req.A, "portfolio": rows}


@app.get("/data/portfolio.csv")
def portfolio_csv_file():
    path = Path(settings.data_dir) / "portfolio.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Сначала запросите рекомендацию.")
    return Response(content=path.read_text(), media_type="text/csv")


# ── Цены ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/recommendation", response_model=RecommendationResponse)
def recommendation(req: RecommendationRequest) -> RecommendationResponse:
    try:
        payload = get_recommendation(
            req.ticker,
            risk_tolerance=req.risk_tolerance,
            investment_horizon_months=req.investment_horizon_months,
            risk_free_rate_annual=req.risk_free_rate_annual,
            beta=req.beta,
            risk_aversion_a=req.risk_aversion_a,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return RecommendationResponse.model_validate(payload)


@app.get("/api/v1/stocks/{symbol}/price-history", response_model=PriceHistoryResponse)
def price_history(symbol: str) -> PriceHistoryResponse:
    safe = symbol.strip()
    if not safe or "/" in safe or ".." in safe:
        raise HTTPException(status_code=400, detail="Некорректный тикер")

    path = Path(settings.data_dir) / f"{safe}.csv"
    try:
        df = load_price_csv(path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Нет файла данных: {path.name}.",
        ) from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    bars = [
        PriceBar(
            date=rec["date"],
            open=rec.get("open"),
            high=rec.get("high"),
            low=rec.get("low"),
            close=float(rec["close"]),
            volume=rec.get("volume"),
        )
        for rec in df.to_dict(orient="records")
    ]
    return PriceHistoryResponse(symbol=safe.upper(), bars=bars)


if PUBLIC_DIR.exists():
    app.mount("/css", StaticFiles(directory=PUBLIC_DIR / "css"), name="css")
    app.mount("/js",  StaticFiles(directory=PUBLIC_DIR / "js"),  name="js")
