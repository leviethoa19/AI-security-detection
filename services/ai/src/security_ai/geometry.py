"""Geometry primitives used by zone context."""

from __future__ import annotations

from security_ai.domain import Point, Zone


def point_in_polygon(point: Point, zone: Zone) -> bool:
    """Return whether a point is inside or on the boundary of a polygon."""

    polygon = zone.polygon
    if len(polygon) < 3:
        raise ValueError("a zone polygon requires at least three points")

    inside = False
    previous = polygon[-1]
    for current in polygon:
        if _point_on_segment(point, previous, current):
            return True

        crosses_scanline = (current.y > point.y) != (previous.y > point.y)
        if crosses_scanline:
            intersection_x = (previous.x - current.x) * (point.y - current.y) / (
                previous.y - current.y
            ) + current.x
            if point.x < intersection_x:
                inside = not inside
        previous = current
    return inside


def _point_on_segment(point: Point, start: Point, end: Point, tolerance: float = 1e-9) -> bool:
    cross_product = (point.y - start.y) * (end.x - start.x) - (point.x - start.x) * (
        end.y - start.y
    )
    if abs(cross_product) > tolerance:
        return False

    return (
        min(start.x, end.x) - tolerance <= point.x <= max(start.x, end.x) + tolerance
        and min(start.y, end.y) - tolerance <= point.y <= max(start.y, end.y) + tolerance
    )

