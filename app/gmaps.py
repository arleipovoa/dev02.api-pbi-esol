"""Google Maps Distance Matrix proxy.

Distance Matrix API does not allow CORS calls from the browser. This module
exposes a thin server-side proxy that injects the Google Maps API key from
configuration and returns the JSON response unchanged.
"""
from typing import Optional

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.logger import logger
from app.security import verify_api_key

router = APIRouter(tags=["Google Maps"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/gmaps/distancematrix", operation_id="gmapsDistanceMatrix")
@limiter.limit("60/minute")
async def gmaps_distance_matrix(
    request: Request,
    origins: str = Query(...),
    destinations: str = Query(...),
    units: str = Query("metric"),
    x_api_key: Optional[str] = Header(None),
):
    if x_api_key is None or not verify_api_key(x_api_key):
        raise HTTPException(status_code=403, detail="Acesso nao autorizado")
    if not settings.GOOGLE_MAPS_API_KEY:
        raise HTTPException(
            status_code=503, detail="GOOGLE_MAPS_API_KEY nao configurada"
        )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={
                    "origins": origins,
                    "destinations": destinations,
                    "units": units,
                    "key": settings.GOOGLE_MAPS_API_KEY,
                },
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout Google Maps")
    except httpx.HTTPError as e:
        logger.error(f"Erro Google Distance Matrix: {e}")
        raise HTTPException(status_code=502, detail="Erro Google Maps")
