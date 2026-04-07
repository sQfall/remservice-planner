import logging
import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "RemServicePlanner/1.0"
TIMEOUT = 5


async def reverse_geocode(lat: float, lon: float) -> str | None:
    """Обратное геокодирование координат через Nominatim."""
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "addressdetails": "1",
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(NOMINATIM_REVERSE_URL, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("display_name")
    except Exception as e:
        logger.error("Ошибка обратного геокодирования (%s, %s): %s", lat, lon, e)
        return None


async def geocode_address(address: str) -> tuple[float, float] | None:
    """Геокодирование адреса через Nominatim OpenStreetMap API."""
    params = {
        "q": address,
        "format": "json",
        "limit": "1",
        "countrycodes": "ru",
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(NOMINATIM_URL, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data and len(data) > 0:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                return (lat, lon)

            logger.warning("Адрес не найден: %s", address)
            return None

    except httpx.TimeoutException:
        logger.error("Таймаут геокодирования адреса: %s", address)
        return None
    except httpx.RequestError as e:
        logger.error("Ошибка запроса к Nominatim для адреса %s: %s", address, e)
        return None
    except (KeyError, ValueError) as e:
        logger.error("Ошибка парсинга ответа Nominatim для адреса %s: %s", address, e)
        return None
