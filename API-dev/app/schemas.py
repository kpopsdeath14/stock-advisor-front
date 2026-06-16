from datetime import date

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    """Запрос рекомендации от фронтенда"""

    ticker: str = Field(..., description="Тикер инструмента .CSV")
    risk_tolerance: str | None = Field(
        None, description="Уровень риска: conservative | moderate | aggressive"
    )
    investment_horizon_months: int | None = Field(
        None, ge=1, description="Горизонт инвестирования в месяцах"
    )
    beta: float | None = Field(
        None,
        description="Бета к индексу",
    )
    risk_aversion_a: float | None = Field(
        None,
        gt=0,
        description="Коэффициент неприятия риска A из модели или задаётся из risk_tolerance",
    )
    risk_free_rate_annual: float | None = Field(
        None,
        ge=0,
        le=0.5,
        description="Безрисковая ставка (годовая)",
    )


class RecommendationResponse(BaseModel):
    """Ответ ML-слоя — структура совпадает с контрактом get_recommendation."""

    ticker: str
    action: str
    confidence: float | None = None
    summary: str | None = None
    factors: list[str] = Field(default_factory=list)
    raw: dict | None = Field(None, description="Произвольный полезный payload от модели")


class PriceBar(BaseModel):
    """Одна точка для графика (линия закрытия или свеча)"""

    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: float | None = None


class PriceHistoryResponse(BaseModel):
    symbol: str
    bars: list[PriceBar]
