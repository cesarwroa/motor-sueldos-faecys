from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

from .repo import find_escala, ym


def months_in_semester(mes_yyyy_mm: str) -> int:
    """Return 1..6 months elapsed in the current semester.
    Jan=1..Jun=6; Jul=1..Dec=6.
    """
    m = ym(mes_yyyy_mm)
    if not m or len(m) < 7:
        return 1
    month = int(m[5:7])
    if 1 <= month <= 6:
        return month
    return month - 6


def antig_pct(rama: str, anios: float) -> float:
    """Antiguedad percent.
    - Agua Potable: 2% acumulativo por anio (treated here as 0.02 * anios)
    - Others: 1% por anio
    """
    r = (rama or "").strip().upper()
    if r == "AGUA POTABLE":
        return 0.02 * anios
    return 0.01 * anios


def calcular_mensual(payload: Dict[str, Any]) -> Dict[str, Any]:
    rama = payload["rama"]
    agrup = payload["agrup"]
    categoria = payload["categoria"]
    mes = payload["mes"]

    anios = float(payload.get("anios_antig", 0) or 0)
    osecac = bool(payload.get("osecac", True))
    afiliado = bool(payload.get("afiliado", False))
    sind_pct = float(payload.get("sind_pct", 0) or 0)
    incluir_sac = bool(payload.get("incluir_sac_proporcional", False))
    adelanto = float(payload.get("adelanto", 0) or 0)

    row = find_escala(rama, agrup, categoria, mes)
    if not row:
        raise ValueError("No se encontro escala para los parametros seleccionados")

    basico = float(row.get("Basico") or 0)
    no_rem = float(row.get("No Remunerativo") or 0)
    suma_fija = float(row.get("SUMA_FIJA") or 0)
    nr_total = no_rem + suma_fija

    apct = antig_pct(rama, anios)
    antig_rem = basico * apct
    antig_nr = nr_total * apct

    pres_rem = (basico + antig_rem) / 12
    pres_nr = (nr_total + antig_nr) / 12

    rem_base = basico + antig_rem + pres_rem
    nr_base = nr_total + antig_nr + pres_nr

    meses_sem = months_in_semester(mes)
    sac_rem = 0.0
    sac_nr = 0.0
    if incluir_sac:
        # Estimacion proporcional del semestre usando el mes como referencia
        factor = meses_sem / 12.0
        sac_rem = rem_base * factor
        sac_nr = nr_base * factor

    # Bases de descuentos segun criterio del sistema:
    base_os_faecys_sind = rem_base + nr_base + sac_rem + sac_nr

    jub = rem_base * 0.11
    pami = rem_base * 0.03
    faecys = base_os_faecys_sind * 0.005
    sindicato = base_os_faecys_sind * (sind_pct / 100.0) if afiliado and sind_pct > 0 else 0.0
    os = base_os_faecys_sind * 0.03 if osecac else 0.0
    osecac_100 = 100.0 if osecac else 0.0

    descuentos = jub + pami + faecys + sindicato + os + osecac_100 + adelanto

    total_rem = rem_base + sac_rem
    total_nr = nr_base + sac_nr
    neto = (total_rem + total_nr) - descuentos

    return {
        "escala": {
            "basico": basico,
            "no_rem": no_rem,
            "suma_fija": suma_fija,
        },
        "conceptos": {
            "antig_rem": antig_rem,
            "antig_nr": antig_nr,
            "presentismo_rem": pres_rem,
            "presentismo_nr": pres_nr,
            "sac_rem": sac_rem,
            "sac_nr": sac_nr,
        },
        "totales": {
            "total_rem": total_rem,
            "total_no_rem": total_nr,
            "descuentos": descuentos,
            "neto": neto,
        },
        "detalles_descuentos": {
            "jubilacion_11": jub,
            "pami_3": pami,
            "faecys_0_5": faecys,
            "sindicato": sindicato,
            "obra_social_3": os,
            "osecac_100": osecac_100,
            "adelanto": adelanto,
        },
        "meta": {
            "meses_semestre": meses_sem,
            "incluye_sac": incluir_sac,
        }
    }
