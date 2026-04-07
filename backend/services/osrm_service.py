import asyncio
import logging
import math
import time
from functools import lru_cache

import httpx

from config import settings

logger = logging.getLogger(__name__)


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками по формуле haversine (метры)."""
    R = 6371000  # радиус Земли в метрах
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _haversine_duration(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Оценка времени в секундах при средней скорости 40 км/ч."""
    distance = _haversine_distance(lat1, lon1, lat2, lon2)
    speed = 40000 / 3600  # 40 км/ч в м/с
    return max(1, int(distance / speed))


class OSRMService:
    def __init__(self):
        self._semaphore: asyncio.Semaphore | None = None
        self._last_request_time: float = 0.0
        self._base_delay = 1.0

        # HTTP-клиент с пулом соединений
        self._client = httpx.AsyncClient(
            timeout=settings.OSRM_TIMEOUT,
            limits=httpx.Limits(
                max_connections=settings.OSRM_CONCURRENCY,
                max_keepalive_connections=5,
            ),
        )

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Ленивая инициализация Semaphore для привязки к event loop."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(settings.OSRM_CONCURRENCY)
        return self._semaphore

    @staticmethod
    def _validate_coords(coords: tuple, name: str) -> None:
        """Валидировать координаты."""
        lon, lat = coords
        if not (-90 <= lat <= 90):
            raise ValueError(f"Invalid latitude in {name}: {lat}")
        if not (-180 <= lon <= 180):
            raise ValueError(f"Invalid longitude in {name}: {lon}")

    @staticmethod
    def _make_cache_key(from_coords: tuple, to_coords: tuple) -> str:
        """Ключ кэша — не зависит от формата API."""
        lon1, lat1 = from_coords
        lon2, lat2 = to_coords
        return f"{lon1:.5f}:{lat1:.5f}-{lon2:.5f}:{lat2:.5f}"

    @staticmethod
    def _make_url_coords(from_coords: tuple, to_coords: tuple) -> str:
        """Строка координат для OSRM URL."""
        lon1, lat1 = from_coords
        lon2, lat2 = to_coords
        return f"{lon1:.5f},{lat1:.5f};{lon2:.5f},{lat2:.5f}"

    async def _throttle(self):
        """Минимальный интервал между запросами к OSRM."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < settings.OSRM_MIN_INTERVAL:
            await asyncio.sleep(settings.OSRM_MIN_INTERVAL - elapsed)
        self._last_request_time = time.monotonic()

    @lru_cache(maxsize=1000)
    def _cached_haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> int:
        """Кэширование haversine для повторяющихся координат."""
        return _haversine_duration(lat1, lon1, lat2, lon2)

    async def _request_osrm(self, url: str, params: dict) -> dict | None:
        """Запрос к OSRM с retry и exponential backoff."""
        for attempt in range(settings.OSRM_MAX_RETRIES):
            try:
                async with self._get_semaphore():
                    response = await self._client.get(url, params=params)
                    response.raise_for_status()

                data = response.json()

                if data.get("code") != "Ok" or not data.get("routes"):
                    logger.warning(
                        "OSRM вернул некорректный ответ для %s: %s", url, data
                    )
                    return None

                route = data["routes"][0]
                return {
                    "duration": route["duration"],  # секунды
                    "distance": route["distance"],  # метры
                    "geometry": route["geometry"],
                }

            except httpx.TimeoutException:
                logger.warning(
                    "Таймаут OSRM (попытка %d/%d): %s", attempt + 1, settings.OSRM_MAX_RETRIES, url
                )
            except httpx.RequestError as e:
                logger.warning(
                    "Ошибка запроса OSRM (попытка %d/%d): %s — %s",
                    attempt + 1,
                    settings.OSRM_MAX_RETRIES,
                    url,
                    e,
                )
            except (KeyError, ValueError) as e:
                logger.error(
                    "Ошибка парсинга ответа OSRM (попытка %d/%d): %s — %s",
                    attempt + 1,
                    settings.OSRM_MAX_RETRIES,
                    url,
                    e,
                )
                return None

            backoff = self._base_delay * (2 ** attempt)
            await asyncio.sleep(backoff)

        return None

    async def get_route(
        self, from_coords: tuple, to_coords: tuple
    ) -> dict | None:
        """Получить маршрут между двумя точками.

        from_coords: (longitude, latitude)
        to_coords: (longitude, latitude)
        Возвращает dict: duration(сек), distance(метры), geometry_json
        """
        self._validate_coords(from_coords, "from_coords")
        self._validate_coords(to_coords, "to_coords")

        cache_key = self._make_cache_key(from_coords, to_coords)

        # Используем lru_cache для haversine
        lon1, lat1 = from_coords
        lon2, lat2 = to_coords
        haversine_result = self._cached_haversine(lat1, lon1, lat2, lon2)

        if settings.OSRM_ENABLED:
            url_coords = self._make_url_coords(from_coords, to_coords)
            url = f"{settings.OSRM_BASE_URL}/{url_coords}"
            params = {"overview": "full", "geometries": "geojson", "steps": "false"}

            result = await self._request_osrm(url, params)
        else:
            result = None

        if result is None:
            # Fallback на haversine — генерируем простую LineString геометрию
            result = {
                "duration": haversine_result,
                "distance": _haversine_distance(lat1, lon1, lat2, lon2),
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon1, lat1], [lon2, lat2]],
                },
            }
            logger.info(
                "Fallback haversine для маршрута %s -> %s", from_coords, to_coords
            )
        else:
            await self._throttle()

        return result

    async def build_distance_matrix(
        self, points: list[tuple]
    ) -> list[list[int]]:
        """Полная матрица длительностей (секунды) между точками.

        points: список (longitude, latitude)
        """
        n = len(points)
        matrix = [[0] * n for _ in range(n)]

        # Собираем только недостающие пары
        tasks_meta = [
            (i, j, points[i], points[j])
            for i in range(n)
            for j in range(n)
            if i != j
        ]

        if not tasks_meta:
            return matrix

        # Действительно параллельные запросы через asyncio.gather
        async def _get_route_safe(from_c, to_c):
            try:
                return await self.get_route(from_c, to_c)
            except Exception as e:
                logger.warning("Ошибка получения маршрута для матрицы: %s", e)
                return None

        results = await asyncio.gather(
            *[_get_route_safe(from_c, to_c) for _, _, from_c, to_c in tasks_meta],
            return_exceptions=True,
        )

        # Заполняем матрицу из результатов
        for idx, (i, j, from_c, to_c) in enumerate(tasks_meta):
            result = results[idx]
            if isinstance(result, Exception) or result is None:
                lon1, lat1 = from_c
                lon2, lat2 = to_c
                matrix[i][j] = self._cached_haversine(lat1, lon1, lat2, lon2)
            else:
                matrix[i][j] = int(result["duration"])

        return matrix

    async def close(self):
        """Закрыить HTTP-клиент при завершении работы."""
        await self._client.aclose()
