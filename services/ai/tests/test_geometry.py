from __future__ import annotations

import pytest

from security_ai.domain import Point, Zone
from security_ai.geometry import point_in_polygon


@pytest.fixture
def square() -> Zone:
    return Zone(
        zone_id="square",
        polygon=(Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)),
    )


@pytest.mark.parametrize(
    ("point", "expected"),
    [
        (Point(5, 5), True),
        (Point(0, 5), True),
        (Point(10, 10), True),
        (Point(-1, 5), False),
        (Point(11, 5), False),
    ],
)
def test_point_in_polygon_includes_boundary(square: Zone, point: Point, expected: bool) -> None:
    assert point_in_polygon(point, square) is expected


def test_polygon_requires_three_points() -> None:
    zone = Zone(zone_id="line", polygon=(Point(0, 0), Point(1, 1)))

    with pytest.raises(ValueError, match="at least three"):
        point_in_polygon(Point(0, 0), zone)

