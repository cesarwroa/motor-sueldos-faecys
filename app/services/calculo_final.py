from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict


def _parse_date(s: str) -> date:
    y, m, d = [int(x) for x in s.split("-")]
    return date(y, m, d)


def years_for_245(fecha_ingreso: str, fecha_egreso: str) -> int:
    """Anios indemnizatorios: anio completo + fraccion >= 3 meses suma 1.

    Regla implementada (criterio que fijaste): >=3 meses.
    """
    di = _parse_date(fecha_ingreso)
    de = _parse_date(fecha_egreso)
    if de <= di:
        return 0

    years = de.year - di.year
    # adjust if anniversary not reached
    anniv = date(di.year + years, di.month, di.day)
    if de < anniv:
        years -= 1
        anniv = date(di.year + years, di.month, di.day)

    # compute remaining months
    months = (de.year - anniv.year) * 12 + (de.month - anniv.month)
    if de.day < anniv.day:
        months -= 1

    return years + (1 if months >= 3 else 0)


def calcular_final(payload: Dict[str, Any]) -> Dict[str, Any]:
    tipo = payload.get("tipo", "DESPIDO_SIN_CAUSA")
    fecha_ingreso = payload.get("fecha_ingreso")
    fecha_egreso = payload.get("fecha_egreso")
    mejor_salario = float(payload.get("mejor_salario") or 0)
    vac_no_gozadas_dias = float(payload.get("vac_no_gozadas_dias") or 0)
    incluir_sac_vac = bool(payload.get("incluir_sac_vac", True))
    preaviso_dias = float(payload.get("preaviso_dias") or 0)
    incluir_sac_preaviso = bool(payload.get("incluir_sac_preaviso", False))

    anios = years_for_245(fecha_ingreso, fecha_egreso) if fecha_ingreso and fecha_egreso else 0

    incluye_245 = (tipo == "DESPIDO_SIN_CAUSA")
    incluye_248 = (tipo == "FALLECIMIENTO")
    incluye_preaviso = (tipo == "DESPIDO_SIN_CAUSA" and preaviso_dias > 0)

    art245 = mejor_salario * anios if incluye_245 else 0.0
    # Art. 248: 50% de la indemnización art. 245 (misma base y años)
    art248 = (mejor_salario * anios * 0.5) if incluye_248 else 0.0

    vac_ind = (mejor_salario / 25.0) * vac_no_gozadas_dias if vac_no_gozadas_dias > 0 else 0.0
    sac_vac = (vac_ind / 12.0) if incluir_sac_vac and vac_ind else 0.0

    preaviso = (mejor_salario * (preaviso_dias / 30.0)) if incluye_preaviso else 0.0
    sac_pre = (preaviso / 12.0) if incluir_sac_preaviso and preaviso else 0.0

    total_ind = art245 + art248 + vac_ind + sac_vac + preaviso + sac_pre

    return {
        "meta": {
            "tipo": tipo,
            "anios_indemnizatorios": anios,
        },
        "conceptos": {
            "indemnizacion_art_245": art245,
            "indemnizacion_art_248": art248,
            "vacaciones_no_gozadas": vac_ind,
            "sac_sobre_vacaciones": sac_vac,
            "preaviso": preaviso,
            "sac_sobre_preaviso": sac_pre,
        },
        "totales": {
            "total_indemnizatorio": total_ind,
            "neto": total_ind,
        }
    }
