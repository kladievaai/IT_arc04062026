from fastapi import FastAPI, HTTPException, Query
from typing import Optional
import httpx
import os

app = FastAPI(
    title="Currency Rate Microservice",
    description="Microservice for getting currency exchange rates",
    version="1.0.0"
)

# Mock exchange rates (fallback / demo mode)
MOCK_RATES = {
    ("USD", "RUB"): 92.5,
    ("EUR", "RUB"): 100.3,
    ("CNY", "RUB"): 12.7,
    ("GBP", "RUB"): 117.8,
    ("USD", "EUR"): 0.921,
    ("EUR", "USD"): 1.085,
    ("RUB", "USD"): 0.0108,
    ("RUB", "EUR"): 0.00997,
}

USE_EXTERNAL_API = os.getenv("USE_EXTERNAL_API", "false").lower() == "true"
EXTERNAL_API_KEY = os.getenv("EXCHANGE_API_KEY", "")
EXTERNAL_API_URL = "https://v6.exchangerate-api.com/v6/{key}/pair/{from_cur}/{to_cur}"


async def get_rate_from_external_api(from_cur: str, to_cur: str) -> float:
    """Fetch rate from external ExchangeRate-API (requires API key in env)."""
    url = EXTERNAL_API_URL.format(
        key=EXTERNAL_API_KEY,
        from_cur=from_cur,
        to_cur=to_cur
    )
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = client.get(url)
        data = response.json()
        if data.get("result") != "success":
            raise ValueError(f"External API error: {data.get('error-type', 'unknown')}")
        return float(data["conversion_rate"])


def get_mock_rate(from_cur: str, to_cur: str) -> float:
    """Return mock/fixed rate. Raises KeyError if pair is unsupported."""
    key = (from_cur.upper(), to_cur.upper())
    if key in MOCK_RATES:
        return MOCK_RATES[key]
    # Try reverse pair and invert
    rev_key = (to_cur.upper(), from_cur.upper())
    if rev_key in MOCK_RATES:
        return round(1.0 / MOCK_RATES[rev_key], 6)
    raise KeyError(f"Unsupported currency pair: {from_cur}/{to_cur}")


@app.get("/rate")
async def get_rate(
    from_currency: str = Query(..., alias="from", description="Source currency code, e.g. USD"),
    to_currency: str = Query(..., alias="to", description="Target currency code, e.g. RUB"),
):
    """
    Returns exchange rate for the given currency pair.

    Example: GET /rate?from=USD&to=RUB → {"from": "USD", "to": "RUB", "rate": 92.5}
    """
    from_currency = from_currency.upper().strip()
    to_currency = to_currency.upper().strip()

    if len(from_currency) != 3 or len(to_currency) != 3:
        raise HTTPException(status_code=400, detail="Currency codes must be 3 characters (ISO 4217)")

    if from_currency == to_currency:
        return {"from": from_currency, "to": to_currency, "rate": 1.0}

    try:
        if USE_EXTERNAL_API and EXTERNAL_API_KEY:
            rate = await get_rate_from_external_api(from_currency, to_currency)
        else:
            rate = get_mock_rate(from_currency, to_currency)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch rate: {str(e)}")

    return {"from": from_currency, "to": to_currency, "rate": rate}


@app.get("/health")
async def health_check():
    """Liveness probe endpoint."""
    return {"status": "ok"}


@app.get("/rates")
async def list_available_rates():
    """Returns all available mock currency pairs."""
    pairs = [{"from": k[0], "to": k[1], "rate": v} for k, v in MOCK_RATES.items()]
    return {"pairs": pairs, "source": "mock" if not USE_EXTERNAL_API else "external"}
