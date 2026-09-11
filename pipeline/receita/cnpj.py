"""CNPJ numérico e alfanumérico (IN RFB nº 2.229/2024, vigente desde jul/2026).

Raiz (8) e ordem (4) aceitam ``0-9A-Z``; o DV (2) continua numérico. Cada
caractere vale ``ord(c) - 48`` (0-9 => 0..9, A-Z => 17..42) e o DV segue o
módulo 11 de sempre. É a mesma regra da macro dbt ``cnpj_dv`` — os testes
garantem que as duas implementações concordam.
"""

from __future__ import annotations

import re

_W1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_W2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_BASE_RE = re.compile(r"^[0-9A-Z]{12}$")
_FULL_RE = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")


def _digit(total: int) -> int:
    r = total % 11
    return 0 if r < 2 else 11 - r


def dv(base12: str) -> str:
    base12 = base12.upper()
    if not _BASE_RE.match(base12):
        raise ValueError(f"base de CNPJ inválida: {base12!r}")
    vals = [ord(c) - 48 for c in base12]
    d1 = _digit(sum(v * w for v, w in zip(vals, _W1, strict=True)))
    d2 = _digit(sum(v * w for v, w in zip([*vals, d1], _W2, strict=True)))
    return f"{d1}{d2}"


def normalize(value: str) -> str:
    """Remove máscara (``12.ABC.345/01DE-35`` -> ``12ABC34501DE35``)."""
    return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()


def is_valid(value: str) -> bool:
    c = normalize(value)
    return bool(_FULL_RE.match(c)) and dv(c[:12]) == c[12:]


def format_cnpj(value: str) -> str:
    c = normalize(value)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else value
