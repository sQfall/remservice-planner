import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import (
    ServiceRequest,
    RequestStatus,
    Priority,
    Brigade,
    DailyPlan,
    RoutePoint,
    RouteSegment,
    GarageSegmentType,
)
from services.planning_service import greedy_planning, _is_brigade_compatible
from services.osrm_service import OSRMService

logger = logging.getLogger(__name__)

PENALTY_BY_PRIORITY = {
    Priority.emergency: 10000000,
    Priority.high: 1000000,
    Priority.medium: 100000,
    Priority.low: 10000,
}

TIME_PER_DEMAND_UNIT = 60  # 1 минута = 60 единиц времени


async def ortools_planning(plan_date: date, db: AsyncSession) -> DailyPlan:
    """Планирование через Google OR-Tools VRPTW."""
    try:
        return await _ortools_core(plan_date, db)
    except Exception as e:
        logger.warning("OR-Tools failed: %s. Fallback to greedy_planning.", e, exc_info=True)
        return await greedy_planning(plan_date, db)


async def _ortools_core(plan_date: date, db: AsyncSession) -> DailyPlan:
    from ortools.constraint_solver import routing_enums_pb2
    from ortools.constraint_solver import pywrapcp

    osrm = OSRMService()

    # 1. Загрузить данные
    day_start = datetime.combine(plan_date, datetime.min.time())
    day_end = datetime.combine(plan_date, datetime.max.time())

    result = await db.execute(
        select(ServiceRequest)
        .where(ServiceRequest.status == RequestStatus.new)
        .where(ServiceRequest.planned_at.between(day_start, day_end))
    )
    requests = list(result.scalars().all())

    if not requests:
        plan = DailyPlan(plan_date=plan_date, status="draft")
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        return plan

    brigades_result = await db.execute(
        select(Brigade).options(selectinload(Brigade.members), selectinload(Brigade.vehicles))
    )
    brigades = list(brigades_result.scalars().all())

    if not brigades:
        plan = DailyPlan(plan_date=plan_date, status="draft")
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        return plan

    # 2. Построить план
    plan = DailyPlan(plan_date=plan_date, status="draft")
    db.add(plan)
    await db.flush()

    # 3. Разделить заявки на совместимые группы для каждой бригады
    # Каждая бригада — свой VRP-маршрут
    brigade_requests_map: dict[int, list[int]] = {}  # brigade_id -> [request_indices]

    for idx, req in enumerate(requests):
        compatible_brigades = [
            b for b in brigades if _is_brigade_compatible(b, req.work_type.value)
        ]
        if compatible_brigades:
            # Назначить первой совместимой бригаде (упрощение)
            brigade_id = compatible_brigades[0].id
            brigade_requests_map.setdefault(brigade_id, []).append(idx)

    unplanned_indices = [
        i for i in range(len(requests))
        if not any(i in indices for indices in brigade_requests_map.values())
    ]

    if unplanned_indices:
        for idx in unplanned_indices:
            logger.warning(
                "Заявка %d (тип=%s) не назначена — нет совместимых бригад",
                requests[idx].id,
                requests[idx].work_type.value,
            )

    # 4. Для каждой бригады решить VRPTW
    total_points_created = 0
    total_segments_created = 0

    for brigade in brigades:
        req_indices = brigade_requests_map.get(brigade.id, [])
        if not req_indices:
            continue

        brigade_requests = [requests[i] for i in req_indices]
        num_locations = len(brigade_requests) + 1  # +1 гараж (депо)

        # Собрать координаты: [гараж, точка1, точка2, ...]
        coords = [
            (brigade.garage_longitude, brigade.garage_latitude),
        ] + [(r.longitude, r.latitude) for r in brigade_requests]

        # Построить матрицу расстояний (в минутах)
        distance_matrix = await osrm.build_distance_matrix(coords)

        # Время обслуживания на каждой точке (минуты работы)
        service_times = [0]  # гараж
        for req in brigade_requests:
            est = req.estimated_duration or 60
            service_times.append(est)

        # Создать OR-Tools модель
        manager = pywrapcp.RoutingIndexManager(num_locations, 1, 0)  # 1 транспорт, депо=0
        routing = pywrapcp.RoutingModel(manager)

        # Callback: transit time
        def transit_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(transit_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Time dimension — разрешаем до конца смены + overtime
        routing.AddDimension(
            transit_callback_index,
            600,  # max overtime (10 часов буфер для гибкости)
            600,    # max route time
            False,
            "Time",
        )
        time_dimension = routing.GetDimensionOrDie("Time")

        # Time windows — смена + overtime
        def _to_minutes(t):
            """Convert time or 'HH:MM:SS' string to minutes from midnight."""
            if isinstance(t, str):
                h, m, s = t.split(':')
                return int(h) * 60 + int(m)
            return t.hour * 60 + t.minute

        shift_start_minutes = _to_minutes(brigade.shift_start)
        shift_end_minutes = _to_minutes(brigade.shift_end) + 60  # +60 min overtime
        shift_limit = datetime.combine(plan_date, datetime.min.time()) + timedelta(minutes=shift_end_minutes)

        depot_index = manager.NodeToIndex(0)
        time_dimension.CumulVar(depot_index).SetRange(shift_start_minutes, shift_end_minutes)

        for i, req in enumerate(brigade_requests):
            node_index = manager.NodeToIndex(i + 1)
            time_dimension.CumulVar(node_index).SetRange(0, shift_end_minutes)
            time_dimension.SlackVar(node_index).SetRange(
                service_times[i + 1],
                service_times[i + 1] + 600,
            )

        # Disjunctions — штрафы за непокрытые заявки
        # Высокие penalty чтобы OR-Tools покрывал все заявки если возможно
        for i, req in enumerate(brigade_requests):
            node_index = manager.NodeToIndex(i + 1)
            penalty = PENALTY_BY_PRIORITY.get(req.priority, 100)
            routing.AddDisjunction([node_index], penalty)

        # Search parameters
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        search_parameters.time_limit.seconds = 30

        # Solve в отдельном потоке чтобы не блокировать asyncio
        import concurrent.futures
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            solution = await loop.run_in_executor(
                executor, routing.SolveWithParameters, search_parameters
            )

        if not solution:
            logger.warning("OR-Tools не нашёл решение для бригады %d", brigade.id)
            continue

        # Извлечь маршрут
        index = routing.Start(0)
        route_order = []
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_order.append(node_index)
            index = solution.Value(routing.NextVar(index))

        route_order.append(manager.IndexToNode(routing.End(0)))  # финальное депо

        # Убрать депо из начала и конца
        route_requests_indices = route_order[1:-1]  # только точки

        # Предел смены: shift_end + 60 мин overtime
        shift_limit = datetime.combine(plan_date, brigade.shift_end) + timedelta(minutes=60)

        # Создать RoutePoint и RouteSegment
        previous_point_id = None
        previous_req = None  # запоминаем предыдущую заявку
        skipped_requests = []  # заявки, которые не влезли в смену

        for seq, node_index in enumerate(route_requests_indices, start=1):
            req = brigade_requests[node_index - 1]

            # Время прибытия (arrival_minutes — минуты от полуночи)
            arrival_minutes = solution.Value(time_dimension.CumulVar(manager.NodeToIndex(node_index)))
            arrival_time = datetime.combine(plan_date, datetime.min.time()) + timedelta(minutes=arrival_minutes)

            est_duration = req.estimated_duration or 60
            departure_time = arrival_time + timedelta(minutes=est_duration)

            # Если departure выходит за лимит смены — пропускаем (останется в new)
            if departure_time > shift_limit:
                skipped_requests.append(req)
                logger.info(
                    "OR-Tools: заявка #%d (%s) пропущена — departure %s > лимит %s",
                    req.id, req.address, departure_time.strftime("%H:%M"), shift_limit.strftime("%H:%M")
                )
                continue

            # RoutePoint
            route_point = RoutePoint(
                request_id=req.id,
                brigade_id=brigade.id,
                plan_id=plan.id,
                sequence=seq,
                arrival_time=arrival_time,
                departure_time=departure_time,
            )
            db.add(route_point)
            await db.flush()

            # RouteSegment от предыдущей точки или от гаража
            if previous_req is None:
                from_coords = (brigade.garage_longitude, brigade.garage_latitude)
            else:
                from_coords = (previous_req.longitude, previous_req.latitude)
            to_coords = (req.longitude, req.latitude)

            route_data = await osrm.get_route(from_coords, to_coords)
            duration_sec = route_data["duration"] if route_data else 600
            duration_min = max(1, int(duration_sec / 60))

            segment = RouteSegment(
                from_point_id=previous_point_id,
                to_point_id=route_point.id,
                duration=duration_min,
                distance=route_data["distance"] if route_data else 0,
                geometry_json=str(route_data["geometry"]) if route_data and route_data.get("geometry") else None,
                is_garage_segment=(previous_point_id is None),
                garage_segment_type=GarageSegmentType.garage_to_first if previous_point_id is None else None,
            )
            db.add(segment)

            # Обновить заявку
            req.status = RequestStatus.planned
            req.planned_at = arrival_time

            previous_point_id = route_point.id
            previous_req = req  # запоминаем для следующего сегмента
            total_points_created += 1
            total_segments_created += 1

        # Финальный сегмент → гараж
        if previous_point_id is not None:
            last_req = brigade_requests[route_requests_indices[-1] - 1]
            route_data = await osrm.get_route(
                (last_req.longitude, last_req.latitude),
                (brigade.garage_longitude, brigade.garage_latitude),
            )

            duration_sec = route_data["duration"] if route_data else 600
            duration_min = max(1, int(duration_sec / 60))

            final_segment = RouteSegment(
                from_point_id=previous_point_id,
                to_point_id=None,
                duration=duration_min,
                distance=route_data["distance"] if route_data else 0,
                geometry_json=str(route_data["geometry"]) if route_data and route_data.get("geometry") else None,
                is_garage_segment=True,
                garage_segment_type=GarageSegmentType.last_to_garage,
            )
            db.add(final_segment)
            total_segments_created += 1

    # 5. Сохранить
    await db.commit()
    await db.refresh(plan)

    # Лог skipped заявок
    all_skipped = []
    for brigade in brigades:
        req_indices = brigade_requests_map.get(brigade.id, [])
        if not req_indices:
            continue
        brigade_requests_list = [requests[i] for i in req_indices]
        # Проверяем какие заявки НЕ получили статус planned
        for req in brigade_requests_list:
            if req.status == RequestStatus.new:
                all_skipped.append(req)

    if all_skipped:
        logger.info(
            "OR-Tools: %d заявок осталось в 'new' (не влезли в смену): %s",
            len(all_skipped),
            ", ".join(f"#{r.id}" for r in all_skipped)
        )

    logger.info(
        "OR-Tools план на %s: %d точек, %d сегментов создано",
        plan_date,
        total_points_created,
        total_segments_created,
    )

    return plan
