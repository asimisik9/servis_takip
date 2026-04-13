from app.database.schemas.route import RouteStop
from app.services.route_service import RouteService


def _stop(student_id: str, lat: float, lng: float, number: str) -> RouteStop:
    return RouteStop(
        student_id=student_id,
        full_name=f"Student {student_id}",
        student_number=number,
        address="Test Address",
        latitude=lat,
        longitude=lng,
        sequence_order=1,
    )


def test_order_stops_geographically_uses_nearest_neighbor_from_origin():
    service = RouteService(db=None)  # type: ignore[arg-type]
    stops = [
        _stop("student-c", 41.1500, 29.0300, "3"),
        _stop("student-a", 41.0010, 29.0010, "1"),
        _stop("student-b", 41.0100, 29.0040, "2"),
    ]

    ordered = service._order_stops_geographically(
        stops=stops,
        origin=(41.0000, 29.0000),
        destination=(41.2000, 29.1000),
        trip_type="to_school",
    )

    assert [stop.student_id for stop in ordered] == ["student-a", "student-b", "student-c"]


def test_order_stops_geographically_keeps_fixed_destination_last_for_from_school():
    service = RouteService(db=None)  # type: ignore[arg-type]
    destination_stop = _stop("student-destination", 41.0010, 29.0010, "1")
    stops = [
        destination_stop,
        _stop("student-mid", 41.0500, 29.0200, "2"),
        _stop("student-far", 41.0900, 29.0400, "3"),
    ]

    ordered = service._order_stops_geographically(
        stops=stops,
        origin=(41.0000, 29.0000),
        destination=(41.0010, 29.0010),
        trip_type="from_school",
    )

    assert ordered[-1].student_id == "student-destination"
