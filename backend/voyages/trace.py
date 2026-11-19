"""Tracé GPS allégé d'un voyage, pour la carte.

Les positions des photos visibles sont ordonnées par date, puis simplifiées
jour par jour avec l'algorithme de Ramer-Douglas-Peucker : on garde les points
qui dessinent la forme du parcours, on retire ceux qui sont presque alignés.
Simplifier par jour garde exacts le premier et le dernier point de chaque
jour, ce qui permet au front de dessiner la portion d'un jour pendant qu'on le
fait défiler.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import date

TOLERANCE_M = 30
DECIMALES = 5  # ~1 m

_RAYON_TERRE_M = 6_371_000


def _projeter(lat: float, lon: float, lat0: float) -> tuple[float, float]:
    """Projection équirectangulaire locale, en mètres : précise à l'échelle d'une journée."""
    x = math.radians(lon) * math.cos(math.radians(lat0)) * _RAYON_TERRE_M
    y = math.radians(lat) * _RAYON_TERRE_M
    return x, y


def _distance_segment(p, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def simplifier(points: list[tuple[float, float]], tolerance_m: float = TOLERANCE_M) -> list[int]:
    """Indices des points (lat, lon) conservés par Ramer-Douglas-Peucker, dans l'ordre."""
    if len(points) <= 2:
        return list(range(len(points)))
    lat0 = sum(p[0] for p in points) / len(points)
    xy = [_projeter(lat, lon, lat0) for lat, lon in points]
    garder = {0, len(points) - 1}
    pile = [(0, len(points) - 1)]
    while pile:  # itératif : pas de limite de récursion sur un long voyage
        debut, fin = pile.pop()
        idx, dmax = None, 0.0
        for i in range(debut + 1, fin):
            d = _distance_segment(xy[i], xy[debut], xy[fin])
            if d > dmax:
                idx, dmax = i, d
        if idx is not None and dmax > tolerance_m:
            garder.add(idx)
            pile += [(debut, idx), (idx, fin)]
    return sorted(garder)


def construire_trace(
    positions: Iterable[tuple[date, float, float]], tolerance_m: float = TOLERANCE_M
) -> list[dict]:
    """[(jour, lat, lon), …] déjà triés par date → [{"lat", "lon", "jour"}, …] allégés."""
    par_jour: dict[date, list[tuple[float, float]]] = {}
    for jour, lat, lon in positions:
        par_jour.setdefault(jour, []).append((lat, lon))
    trace = []
    for jour, points in par_jour.items():
        for i in simplifier(points, tolerance_m):
            lat, lon = points[i]
            trace.append({"lat": round(lat, DECIMALES), "lon": round(lon, DECIMALES), "jour": jour.isoformat()})
    return trace
