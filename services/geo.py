import math


_PI = math.pi
_A = 6378245.0
_EE = 0.006693421622965943


def _outside_china(longitude: float, latitude: float) -> bool:
    return not (72.004 <= longitude <= 137.8347 and 0.8293 <= latitude <= 55.8271)


def _transform_latitude(longitude: float, latitude: float) -> float:
    value = -100.0 + 2.0 * longitude + 3.0 * latitude
    value += 0.2 * latitude * latitude + 0.1 * longitude * latitude
    value += 0.2 * math.sqrt(abs(longitude))
    value += (20.0 * math.sin(6.0 * longitude * _PI) + 20.0 * math.sin(2.0 * longitude * _PI)) * 2.0 / 3.0
    value += (20.0 * math.sin(latitude * _PI) + 40.0 * math.sin(latitude / 3.0 * _PI)) * 2.0 / 3.0
    value += (160.0 * math.sin(latitude / 12.0 * _PI) + 320 * math.sin(latitude * _PI / 30.0)) * 2.0 / 3.0
    return value


def _transform_longitude(longitude: float, latitude: float) -> float:
    value = 300.0 + longitude + 2.0 * latitude
    value += 0.1 * longitude * longitude + 0.1 * longitude * latitude
    value += 0.1 * math.sqrt(abs(longitude))
    value += (20.0 * math.sin(6.0 * longitude * _PI) + 20.0 * math.sin(2.0 * longitude * _PI)) * 2.0 / 3.0
    value += (20.0 * math.sin(longitude * _PI) + 40.0 * math.sin(longitude / 3.0 * _PI)) * 2.0 / 3.0
    value += (150.0 * math.sin(longitude / 12.0 * _PI) + 300.0 * math.sin(longitude / 30.0 * _PI)) * 2.0 / 3.0
    return value


def wgs84_to_gcj02(longitude: float, latitude: float) -> tuple[float, float]:
    """Convert browser/GPS WGS-84 coordinates to the system used by Amap in China."""
    if _outside_china(longitude, latitude):
        return longitude, latitude
    latitude_delta = _transform_latitude(longitude - 105.0, latitude - 35.0)
    longitude_delta = _transform_longitude(longitude - 105.0, latitude - 35.0)
    rad_latitude = latitude / 180.0 * _PI
    magic = math.sin(rad_latitude)
    magic = 1 - _EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    latitude_delta = latitude_delta * 180.0 / ((_A * (1 - _EE)) / (magic * sqrt_magic) * _PI)
    longitude_delta = longitude_delta * 180.0 / (_A / sqrt_magic * math.cos(rad_latitude) * _PI)
    return longitude + longitude_delta, latitude + latitude_delta
