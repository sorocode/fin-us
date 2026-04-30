from typing import Any
from pydantic import BaseModel, Field

class TradingSignal(BaseModel):
    decision: str = Field(..., description="BUY, SELL, 또는 HOLD")
    confidence_score: float = Field(..., ge=0, le=1)
    reason: str
    target_stock: str


class AnalysisReport(BaseModel):
    summary: str
    details: TradingSignal
    source_news: list[str]
    trading_trend: str | None = None


class CommonResponse(BaseModel):
    status: str = "success"
    data: dict[str, Any] | None = None
    message: str | None = None
