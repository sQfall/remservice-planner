import asyncio
import json
import logging
import math
import time

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://router.project-osrm.org/route/v1/driving"


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
        self._cache: dict = {}
        self._semaphore = asyncio.Semaphore(5)
        self._delay = 0.2
        self._max_retries = 2
        self._base_delay = 1.0
        self._use_osrm = True  # реальные маршруты по дорогам через OSRM

    def _make_key(self, from_coords: tuple, to_coords: tuple) -> str:
        lon1, lat1 = from_coords
        lon2, lat2 = to_coords
        # Валидация координат
        if not (-90 <= lat1 <= 90) or not (-180 <= lon1 <= 180):
            raise ValueError(f"Invalid from_coords: {from_coords}")
        if not (-90 <= lat2 <= 90) or not (-180 <= lon2 <= 180):
            raise ValueError(f"Invalid to_coords: {to_coords}")
        return f"{lon1:.5f},{lat1:.5f};{lon2:.5f},{lat2:.5f}"

    async def _request_osrm(self, coords_str: str) -> dict | None:
        url = f"{BASE_URL}/{coords_str}"
        params = {"overview": "full", "geometries": "geojson", "steps": "false"}

        for attempt in range(self._max_retries):
            try:
                async with self._semaphore:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        response = await client.get(url, params=params)
                        response.raise_for_status()

                data = response.json()

                if data.get("code") != "Ok" or not data.get("routes"):
                    logger.warning(
                        "OSRM вернул некорректный ответ для %s: %s", coords_str, data
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
                    "Таймаут OSRM (попытка %d/%d): %s", attempt + 1, self._max_retries, coords_str
                )
            except httpx.RequestError as e:
                logger.warning(
                    "Ошибка запроса OSRM (попытка %d/%d): %s — %s",
                    attempt + 1,
                    self._max_retries,
                    coords_str,
                    e,
                )
            except (KeyError, ValueError) as e:
                logger.error(
                    "Ошибка парсинга ответа OSRM (попытка %d/%d): %s — %s",
                    attempt + 1,
                    self._max_retries,
                    coords_str,
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
        key = self._make_key(from_coords, to_coords)

        if key in self._cache:
            return self._cache[key]

        if self._use_osrm:
            result = await self._request_osrm(key)
        else:
            result = None

        if result is None:
            # Fallback на haversine — генерируем простую LineString геометрию
            lon1, lat1 = from_coords
            lon2, lat2 = to_coords
            result = {
                "duration": _haversine_duration(lat1, lon1, lat2, lon2),
                "distance": _haversine_distance(lat1, lon1, lat2, lon2),
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon1, lat1], [lon2, lat2]],
                },
            }
            logger.info(
                "Fallback haversine для маршрута %s -> %s", from_coords, to_coords
            )

        self._cache[key] = result
        await asyncio.sleep(self._delay)
        return result

    async def build_distance_matrix(
        self, points: list[tuple]
    ) -> list[list[int]]:
        """Полная матрица длительностей (секунды) между точками.

        points: список (longitude, latitude)
        """
        n = len(points)
        matrix = [[0] * n for _ in range(n)]

        tasks = []
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                key = self._make_key(points[i], points[j])
                if key in self._cache:
                    matrix[i][j] = int(self._cache[key]["duration"])
                else:
                    tasks.append((i, j, points[i], points[j]))

        # Запросить все недоста маршрутов параллельно
        for i, j, from_c, to_c in tasks:
            result = await self.get_route(from_c, to_c)
            if result:
                matrix[i][j] = int(result["duration"])
            else:
                lon1, lat1 = from_c
                lon2, lat2 = to_c
                matrix[i][j] = _haversine_duration(lat1, lon1, lat2, lon2)

        return matrix
