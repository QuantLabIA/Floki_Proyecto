"""Reglas horarias de acceso que no dependen de Flask."""
from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

ARGENTINA_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

FREE_ENTRY_CUTOFF = time(3, 30)
COMMON_FREE_CUTOFF = FREE_ENTRY_CUTOFF
FREE_ENTRY_CUTOFF_LABEL = "03:30"
COMMON_FREE_CUTOFF_LABEL = FREE_ENTRY_CUTOFF_LABEL

BIRTHDAY_DISCOUNT_CUTOFF = time(3, 0)
BIRTHDAY_DISCOUNT_CUTOFF_LABEL = "03:00"


def _night_window_available(cutoff: time, now_value: datetime | None = None) -> bool:
    """Evalúa una franja nocturna que comienza al mediodía y cruza medianoche."""
    now_value = now_value or datetime.now(ARGENTINA_TZ).replace(tzinfo=None)
    current_time = now_value.time().replace(second=0, microsecond=0)
    return current_time >= time(12, 0) or current_time < cutoff


def free_entry_available(now_value: datetime | None = None) -> bool:
    """FREE válido hasta las 03:29; a las 03:30 queda bloqueado."""
    return _night_window_available(FREE_ENTRY_CUTOFF, now_value)


def common_list_free_available(now_value: datetime | None = None) -> bool:
    """Alias conservado para compatibilidad con versiones anteriores."""
    return free_entry_available(now_value)


def birthday_discount_available(now_value: datetime | None = None) -> bool:
    """50% OFF de cumpleaños válido hasta las 02:59; a las 03:00 finaliza."""
    return _night_window_available(BIRTHDAY_DISCOUNT_CUTOFF, now_value)
