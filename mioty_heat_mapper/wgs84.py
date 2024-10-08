from __future__ import annotations

import math


class Coord:
    """
    Represents a WGS84 coordinate (latitude, longitude).
    """

    def __init__(self, lat: float, lon: float) -> None:
        self._lat = lat
        self._lon = lon

    def __add__(self, other: Coord) -> Coord:
        return Coord(self._lat + other._lat, self._lon + other._lon)

    def __sub__(self, other: Coord) -> Coord:
        return Coord(self._lat - other._lat, self._lon - other._lon)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Coord):
            return False
        return almost_eq(self._lat, other._lat) and almost_eq(
            self._lon, other._lon
        )

    def __repr__(self) -> str:
        return f"Coord({self._lon} lon, {self._lat} lat)"

    def lat(self) -> float:
        return self._lat

    def lon(self) -> float:
        return self._lon

    def rot_around_zero(self, phi: float) -> Coord:
        """
        Rotates the coordinate around the origin (0,0) (clockwise).
        """

        # Rotation matrix recap:
        # |a b| = | cos(phi)  -sin(phi) |
        # |c d|   | sin(phi)   cos(phi) |
        return Coord(
            math.cos(phi) * self._lat - math.sin(phi) * self._lon,
            math.sin(phi) * self._lat + math.cos(phi) * self._lon,
        )

    def skew_lon(self, skew: float) -> Coord:
        """
        Skews the coordinate along X-axis (lon-axis)
        """

        return Coord(
            self._lat,
            self._lon + skew * self._lat,
        )


class World:
    """
    Represents a world section by its corners.

    This section should be small enough to be approximately flat (i.e. not
    affected by the curvature of the earth), for the conversions between an X/Y
    coordinate space to a WGS84 coordinate to be valid.

    The two coordinate spaces look a little like the following:

    ```
    Image placed in WGS84         Image placed in X/Y

    lat                           y
    ^                             ^
    │ ● p3                        │
    │  \\              _● p2       ● q3
    │   \\          _-¯            │
    │    \\      _-¯               │ height
    │     \\  _-¯                  │
    │   p1 ●¯                     │
    │                             │     width
    ┼──────────────────────>   q1 ●────────────────●─q2──>
                         lon                             x
    ```
    """

    def __init__(
        self,
        wgs_corners: tuple[Coord, Coord, Coord],
        width: float,
        height: float,
    ):
        self.wgs_bottom_left = wgs_corners[0]
        """Point p1 (bottom left corner)."""
        self.wgs_bottom_right = wgs_corners[1]
        """Point p2 (bottom right corner)."""
        self.wgs_top_left = wgs_corners[2]
        """Point p3 (top left corner)."""

        self.width = width
        self.height = height

        p1 = self.wgs_bottom_left
        p2 = self.wgs_bottom_right
        p3 = self.wgs_top_left

        self.trans = Coord(-p1._lat, -p1._lon)

        if p1 == p2 or p1 == p3 or p2 == p3:
            raise Exception("The WGS84 corners are not sufficiently far apart.")

        # Translate p1 into coordinate origin
        p3 = p3 - p1
        p2 = p2 - p1
        p1 = p1 - p1
        if not almost_eq(p1._lat, 0.0) or not almost_eq(p1._lon, 0.0):
            raise Exception(f"Could not translate coords to zero: {p1}")

        # Rotate p2 onto x-axis
        phi1 = math.atan2(p2._lat, p2._lon)
        p2 = p2.rot_around_zero(phi1)
        p3 = p3.rot_around_zero(phi1)

        if not almost_eq(p2._lat, 0.0):
            raise Exception(f"Could not rotate coords around zero: {p2}")
        if p2._lat < 0.0:
            raise Exception(f"Rotated coords in the wrong direction: {p2}")

        # Skew p3 onto y-axis
        phi2 = math.atan2(p3._lat, p3._lon)
        if abs(phi2) > math.pi * 0.9:
            raise Exception(f"Coordinate system skew unreasonably large: {p3}")

        skew = p3._lon / p3._lat
        if abs(skew) > 1.0:
            raise Exception(
                f"Coordinate system skew is more than 45 deg: {p3} / k={skew}"
            )

        p3 = p3.skew_lon(-skew)
        if not almost_eq(p3._lon, 0.0):
            raise Exception(f"Could not skew coords to rectangular shape: {p3}")
        if p3._lat < 0.0:
            raise Exception(f"Coordinate system is flipped: {p3}")

        self.skew = skew
        self.phi = phi1

        # Stretch rectangles
        self.stretch_x = p2._lon / width
        self.stretch_y = p3._lat / height

    def to_wgs(self, x: float, y: float) -> Coord:
        # Un-stretch
        c = Coord(y * self.stretch_y, x * self.stretch_x)

        # Un-skew
        c = c.skew_lon(self.skew)

        # Un-rotate
        c = c.rot_around_zero(-self.phi)

        # Un-translate
        c = c - self.trans

        return c


def almost_eq(f1: float, f2: float) -> bool:
    """
    See: https://stackoverflow.com/questions/33024258/compare-two-floats-for-equality-in-python
    """
    tol = 1e-6
    return abs(f1 - f2) < max(tol, tol * max(abs(f1), abs(f2)))


def sanity_check_impl() -> None:
    p1 = Coord(47.188770353504495, 8.679289310900968)
    p2 = Coord(47.18841891486276, 8.680867011940794)
    p3 = Coord(47.189467267318214, 8.679525966056941)
    world = World((p1, p2, p3), 800, 600)

    if not world.to_wgs(0, 0) == p1:
        print("Expected:", p1)
        raise Exception("Wrong coordinate transform (0,0).")

    if not world.to_wgs(800, 0) == p2:
        print("Expected:", p2)
        raise Exception("Wrong coordinate transform (800, 0).")

    if not world.to_wgs(0, 600) == p3:
        print("Expected:", p3)
        raise Exception("Wrong coordinate transform (0, 600).")
