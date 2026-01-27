from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import datetime as dt
import math

import escalas

from escalas import find_row


def _f(x: Any) -> float:
    try:
        if x is None:
            return 0.0
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            return float(x)
        s = str(x).strip().replace("$", "").replace(" ", "")
        # 1.234,56 -> 1234.56
        if s.count(",") == 1 and s.count(".") >= 1:
            s = s.replace(".", "").replace(",", ".")
        elif s.count(",") == 0 and s.count(".") >= 1:
            # 3.208.680 -> 3208680
            s = s.replace(".", "")
        else:
            s = s.replace(",", ".")
        return float(s) if s else 0.0
    except Exception:
        return 0.0


def _r2(x: float) -> float:
    return float(f"{x:.2f}")


def _fmt_pct(x: float) -> str:
    """Formatea un porcentaje para etiqueta (1.0 -> '1', 1.5 -> '1.5')."""
    try:
        xf = float(x)
    except Exception:
        return str(x)
    if abs(xf - round(xf)) < 1e-9:
        return str(int(round(xf)))
    s = f"{xf:.2f}".rstrip('0').rstrip('.')
    return s


def _u(s: Any) -> str:
    return (str(s or "").strip().upper())


def _parse_date(s: Any) -> Optional[dt.date]:
    if not s:
        return None
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _is_call(rama: str) -> bool:
    return _u(rama) in ("CALL CENTER", "CENTRO DE LLAMADAS")


def _is_agua(rama: str) -> bool:
    return _u(rama) == "AGUA POTABLE"


def _is_turismo(rama: str) -> bool:
    return _u(rama) == "TURISMO"


def _is_cereales(rama: str) -> bool:
    return _u(rama) == "CEREALES"


def _is_funebres(rama: str) -> bool:
    return _u(rama) in ("FUNEBRES", "FÚNEBRES")


# Horas nocturnas: recargo 13,33% (1h nocturna = 1h 8m)
NOCT_RECARGO = 8.0 / 60.0  # 0.133333...


# Turismo (CCT 547/08) - Adicional por KM (valores por km, según escala 01/2026 a 05/2026)
TUR_KM_RATES: Dict[str, Dict[str, Dict[str, float]]] = {
    "2026-01": {
        "C4": {"menos100": 112.31, "mas100": 129.16},
        "C5": {"menos100": 110.62, "mas100": 127.21},
    },
    "2026-02": {
        "C4": {"menos100": 112.31, "mas100": 129.16},
        "C5": {"menos100": 110.62, "mas100": 127.21},
    },
    "2026-03": {
        "C4": {"menos100": 112.31, "mas100": 129.16},
        "C5": {"menos100": 110.62, "mas100": 127.21},
    },
    "2026-04": {
        "C4": {"menos100": 112.31, "mas100": 129.16},
        "C5": {"menos100": 110.62, "mas100": 127.21},
    },
    "2026-05": {
        "C4": {"menos100": 122.31, "mas100": 140.66},
        "C5": {"menos100": 120.62, "mas100": 138.71},
    },
}


def _tur_km_importe(mes: str, tipo: str, km_menos100: int, km_mas100: int) -> float:
    t = (tipo or "").strip().upper()
    mm = (mes or "").strip()
    d = (TUR_KM_RATES.get(mm) or {}).get(t) or {}
    v1 = float(d.get("menos100") or 0.0)
    v2 = float(d.get("mas100") or 0.0)
    return (float(km_menos100 or 0) * v1) + (float(km_mas100 or 0) * v2)


def _vac_anuales_por_antig(anios: int) -> int:
    if anios < 5:
        return 14
    if anios < 10:
        return 21
    if anios < 20:
        return 28
    return 35


# (sin pandas)

def _funebres_adicionales(mes: str, flags: Dict[str, Any], basico_prorrateado: float, factor_hs: float) -> float:
    """Suma adicionales Fúnebres según maestro y flags del frontend (funAdic1..N).

    - Si el item es porcentaje: se aplica sobre el básico prorrateado.
    - Si el item es monto: se prorratea por factor_hs.
    """
    data = escalas.get_adicionales_funebres(mes)
    items = data.get("items") or []
    total = 0.0
    for i, it in enumerate(items, start=1):
        flag = flags.get(f"funAdic{i}")
        if isinstance(flag, str):
            flag = flag.lower() in ("1", "true", "si", "sí", "on")
        if not bool(flag):
            continue
        tipo = (it.get("tipo") or "monto").lower()
        if tipo == "pct":
            total += basico_prorrateado * (float(it.get("pct") or 0.0) / 100.0)
        else:
            total += float(it.get("monto") or 0.0) * factor_hs
    return total


def _conex_pct(conex: int) -> float:
    res = escalas.match_regla_conexiones(int(conex or 0))
    if not res.get("ok"):
        return 0.0
    return float(res.get("pct") or 0.0)


def _ant_factor(rama: str, anios: int) -> float:
    if anios <= 0:
        return 0.0
    if _is_agua(rama):
        # 2% acumulativo
        return (math.pow(1.02, anios) - 1.0)
    return 0.01 * anios


def _find_basico_ref(mes: str, rama_pref: str, cats: List[str]) -> float:
    """Básicos de referencia para adicionales históricos (CCT 130/75 - Acuerdo 26/09/1983).

    Se intenta en la rama actual y luego en GENERAL. Para cada rama,
    se prueba en agrups comunes (GENERAL y —) y con las variantes de categorías.
    """
    rama_pref_u = _u(rama_pref)
    ramas_try = [rama_pref_u]
    if rama_pref_u != "GENERAL":
        ramas_try.append("GENERAL")
    for rr in ramas_try:
        for agr in ("GENERAL", "—"):
            for cat in cats:
                row = find_row(rr, agr, cat, mes)
                if row:
                    return _f(row.get("basico"))
    return 0.0


def _base_aportes(rem: float, nr: float, viaticos_nr: float) -> float:
    # Viáticos NR se excluyen de aportes
    return max(0.0, (rem + nr) - viaticos_nr)


def _add(items: List[Dict[str, Any]], concepto: str, rem=0.0, nr=0.0, ind=0.0, ded=0.0, base=0.0):
    """Agrega una fila al recibo.

    Compatibilidad con el HTML (campos r/n/i/d) + nombres explícitos.
    """
    items.append({
        "concepto": concepto,
        "base": _r2(base if base else (rem or nr or ind or ded)),

        # === Compat (HTML) ===
        "r": _r2(rem),
        "n": _r2(nr),
        "i": _r2(ind),
        "d": _r2(ded),

        # === Nombres explícitos (por si el front cambia) ===
        "remunerativo": _r2(rem),
        "no_remunerativo": _r2(nr),
        "indemnizatorio": _r2(ind),
        "deduccion": _r2(ded),
    })


def calcular_recibo(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Server-side calculator.
    Devuelve:
      { ok, modo, items[], totales{remunerativo,no_remunerativo,deducciones,neto} }
    """
    rama = payload.get("rama")
    agrup = payload.get("agrup") or "—"
    categoria = payload.get("categoria")
    mes = payload.get("mes")

    if not rama or not categoria or not mes:
        return {"ok": False, "error": "Faltan rama/categoria/mes"}

    # Modo mensual o final
    modo = _u(payload.get("modo") or "MENSUAL")
    if modo == "FINAL":
        return _calcular_final(payload)

    row = find_row(rama, agrup, categoria, mes)
    if not row:
        return {"ok": False, "error": "No se encontró Rama/Agrup/Categoría/Mes en el maestro"}

    hs = _f(payload.get("hs") or 48) or 48
    hs = max(1.0, min(48.0, hs))

    anios = int(_f(payload.get("anios") or 0) or 0)
    zona_pct = _f(payload.get("zona_pct") or 0)
    presentismo_ok = bool(payload.get("presentismo", True))

    basico = _f(row.get("basico") or 0.0)
    # Maestro actual: NR consolidado en "suma_fija" (y opcionalmente "no_rem")
    nr_base = _f(row.get("no_rem") or 0.0)
    suma_fija = _f(row.get("suma_fija") or 0.0)
    nr1 = 0.0
    nr2 = suma_fija

    # Prorrateo por hs: Call Center y Menores Cereales NO
    factor_hs = 1.0
    if not _is_call(rama) and not (_is_cereales(rama) and "MENORES" in _u(categoria)):
        factor_hs = hs / 48.0

    basico *= factor_hs
    nr_base *= factor_hs
    nr1 *= factor_hs
    nr2 *= factor_hs

    # ---- Adicionales históricos (CCT 130/75 - Acuerdo 26/09/1983)
    # Vidrierista (3,83% sobre básico inicial Vendedor B)
    armado_vidriera = bool(payload.get("armado_vidriera"))
    armado_rem = 0.0
    if armado_vidriera:
        base_vend_b = _find_basico_ref(mes, rama, ["Vendedor B", "VENDEDOR B"])
        armado_rem = base_vend_b * 0.0383 * factor_hs

    # Cajeros (Art. 30): A/C 12,25% sobre básico inicial Cajeros A; B 48% sobre básico inicial Cajeros B
    manejo_caja = bool(payload.get("manejo_caja"))
    cajero_tipo = str(payload.get("cajero_tipo") or "").strip().upper()
    manejo_caja_rem = 0.0
    if manejo_caja and cajero_tipo in ("A", "B", "C"):
        if cajero_tipo == "B":
            base_caj = _find_basico_ref(mes, rama, ["Cajeros B", "CAJEROS B"])
            manejo_caja_rem = base_caj * 0.48 * factor_hs
        else:
            base_caj = _find_basico_ref(mes, rama, ["Cajeros A", "CAJEROS A"])
            manejo_caja_rem = base_caj * 0.1225 * factor_hs

    # Adicional por KM:
    # - Rama TURISMO (CCT 547/08): valores fijos por km, por categoría (C4 / C5) y mes.
    # - Resto de ramas (CCT 130/75 - Art. 36): % por km sobre básicos iniciales de categorías referencia.
    km_tipo = str(payload.get("km_tipo") or "").strip().upper()
    km_menos100 = int(_f(payload.get("km_menos100") or 0) or 0)
    km_mas100 = int(_f(payload.get("km_mas100") or 0) or 0)
    km_rem = 0.0
    km_label = ""
    if (km_menos100 > 0 or km_mas100 > 0):
        if _is_turismo(rama):
            tipo = km_tipo
            if tipo not in ("C4", "C5"):
                cu = _u(categoria)
                if "C4" in cu:
                    tipo = "C4"
                elif "C5" in cu:
                    tipo = "C5"
            km_rem = _tur_km_importe(mes, tipo, km_menos100, km_mas100)
            km_label = f"Adicional por KM (Operativo {tipo})" if tipo in ("C4", "C5") else "Adicional por KM"
        else:
            if km_tipo in ("AY", "CH"):
                if km_tipo == "AY":
                    b1 = _find_basico_ref(mes, rama, ["Auxiliar A", "PERSONAL AUXILIAR A"])
                    b2 = _find_basico_ref(mes, rama, ["Auxiliar Especializado A", "AUXILIAR ESPECIALIZADO A"])
                    km_rem = (b1 * (0.0082 / 100.0) * km_menos100) + (b2 * (0.01 / 100.0) * km_mas100)
                    km_label = "Adicional por KM (Ayudante de Chofer)"
                else:
                    b1 = _find_basico_ref(mes, rama, ["Auxiliar B", "PERSONAL AUXILIAR B"])
                    b2 = _find_basico_ref(mes, rama, ["Auxiliar Especializado B", "AUXILIAR ESPECIALIZADO B"])
                    km_rem = (b1 * (0.01 / 100.0) * km_menos100) + (b2 * (0.0115 / 100.0) * km_mas100)
                    km_label = "Adicional por KM (Chofer)"

    ant_fac = _ant_factor(rama, anios)
    ant_rem = basico * ant_fac
    ant_nr = nr_base * ant_fac

    zona_rem = (basico + ant_rem) * (zona_pct / 100.0)

    # Turismo título
    tur_pct = _f(payload.get("tur_titulo_pct") or 0) / 100.0
    tit_rem = (basico * tur_pct) if (_is_turismo(rama) and tur_pct > 0) else 0.0
    tit_nr = (nr_base * tur_pct) if (_is_turismo(rama) and tur_pct > 0) else 0.0

    # Agua conexiones
    conex = int(_f(payload.get("agua_conex") or 0) or 0)
    conex_pct = _conex_pct(conex) if _is_agua(rama) else 0.0
    conex_rem = basico * conex_pct
    conex_nr = nr_base * conex_pct

    # Fúnebres adicionales (rem)
    fun_rem = _funebres_adicionales(mes, payload) if _is_funebres(rama) else 0.0

    # A cuenta (rem) / Viáticos (nr sin aportes)
    a_cuenta = _f(payload.get("a_cuenta") or 0)
    viaticos_nr = _f(payload.get("viaticos_nr") or 0)

    # Faltante/Embargo
    faltante = _f(payload.get("faltante") or 0)
    embargo = _f(payload.get("embargo") or 0)

    # Horas extras + nocturnas (cálculo sobre “hora” de rem y de nr)
    # Divisor 200 (mensualizado 48hs)
    base_pre = basico + ant_rem + zona_rem + a_cuenta + tit_rem + conex_rem + fun_rem + armado_rem + manejo_caja_rem + km_rem
    base_nr_pre = nr_base + ant_nr + tit_nr + conex_nr

    hora_rem = (base_pre / 200.0) if base_pre else 0.0
    hora_nr = (base_nr_pre / 200.0) if base_nr_pre else 0.0

    hex50 = _f(payload.get("hex50") or 0)
    hex100 = _f(payload.get("hex100") or 0)
    noct = _f(payload.get("noct") or 0)

    hex50_rem = hora_rem * 1.5 * hex50
    hex50_nr = hora_nr * 1.5 * hex50
    hex100_rem = hora_rem * 2.0 * hex100
    hex100_nr = hora_nr * 2.0 * hex100
    noct_rem = hora_rem * NOCT_RECARGO * noct
    noct_nr = hora_nr * NOCT_RECARGO * noct

    # Feriados trabajados/no trabajados (simple)
    fer_no = int(_f(payload.get("fer_no") or 0) or 0)
    fer_si = int(_f(payload.get("fer_si") or 0) or 0)
    dia_rem_25 = base_pre / 25.0 if base_pre else 0.0
    dia_nr_25 = base_nr_pre / 25.0 if base_nr_pre else 0.0
    fer_no_rem = dia_rem_25 * fer_no
    fer_si_rem = dia_rem_25 * fer_si
    fer_si_nr = dia_nr_25 * fer_si

    # Vacaciones gozadas (dif 25/30)
    vac_goz = _f(payload.get("vac_goz") or 0)
    vac_add_rem = base_pre * (1/25 - 1/30) * vac_goz if vac_goz else 0.0
    vac_add_nr = base_nr_pre * (1/25 - 1/30) * vac_goz if vac_goz else 0.0

    # Licencia sin goce / suspensión (ded)
    lic_sg = _f(payload.get("lic_sg") or 0)
    ded_lic = ((base_pre + base_nr_pre) / 30.0) * lic_sg if lic_sg else 0.0

    # Ausencias injustificadas (ded) - regla: día=(Básico+Antig+Zona)/30
    aus = _f(payload.get("aus") or 0)
    ded_aus = ((basico + ant_rem + zona_rem) / 30.0) * aus if aus else 0.0
    if aus > 1:
        presentismo_ok = False

    # Presentismo
    pres_rem = (base_pre / 12.0) if presentismo_ok else 0.0
    pres_nr = (base_nr_pre / 12.0) if presentismo_ok else 0.0

    total_rem = base_pre + pres_rem + hex50_rem + hex100_rem + noct_rem + fer_no_rem + fer_si_rem + vac_add_rem
    total_nr = base_nr_pre + pres_nr + hex50_nr + hex100_nr + noct_nr + fer_si_nr + vac_add_nr + viaticos_nr

    # Deducciones según reglas del sistema:
    # Jubilación 11% y PAMI 3% SOLO sobre Rem.
    # OSECAC/FAECYS/Sindicato sobre Rem + NR (excepto viáticos NR).
    jubilado = bool(payload.get("jubilado"))
    afiliado = bool(payload.get("afiliado"))
    osecac = bool(payload.get("osecac", True))

    sind_pct = _f(payload.get("sind_pct") or 0) or 0.0
    sind_fijo = _f(payload.get("sind_fijo") or 0) or 0.0

    base_ap = _base_aportes(total_rem, total_nr, viaticos_nr)

    # Regla del sistema (admin): si es JUBILADO, no se descuenta PAMI ni Obra Social,
    # pero sí Jubilación 11% (y los aportes solidarios/afiliación que correspondan).
    jub = total_rem * 0.11
    pami = 0.0 if jubilado else total_rem * 0.03

    os_3 = 0.0
    os_100 = 0.0
    if osecac and (not jubilado):
        os_3 = base_ap * 0.03
        os_100 = 100.0

    faecys = base_ap * 0.005
    sind_solid = base_ap * 0.02
    afil_pct = base_ap * (sind_pct / 100.0) if (afiliado and sind_pct > 0) else 0.0
    afil_fijo = sind_fijo if (afiliado and sind_fijo > 0) else 0.0

    total_ded = jub + pami + os_3 + os_100 + faecys + sind_solid + afil_pct + afil_fijo + ded_lic + ded_aus + faltante + embargo
    neto = (total_rem + total_nr) - total_ded

    items: List[Dict[str, Any]] = []
    _add(items, "Básico", rem=basico, base=basico)
    if ant_rem or ant_nr:
        _add(items, "Antigüedad", rem=ant_rem, nr=ant_nr, base=basico + nr_base)
    if zona_rem:
        _add(items, f"Zona desfavorable ({_r2(zona_pct)}%)", rem=zona_rem, base=basico + ant_rem)
    if tit_rem or tit_nr:
        _add(items, "Adicional por Título", rem=tit_rem, nr=tit_nr, base=basico + nr_base)
    if conex_rem or conex_nr:
        _add(items, f"Adicional por conexiones ({conex})", rem=conex_rem, nr=conex_nr, base=basico + nr_base)
    if fun_rem:
        _add(items, "Adicionales Fúnebres", rem=fun_rem, base=fun_rem)
    if armado_rem:
        _add(items, "Armado de vidriera (3,83%)", rem=armado_rem, base=armado_rem)
    if manejo_caja_rem:
        _add(items, f"Manejo de Caja (Art. 30 - {cajero_tipo})", rem=manejo_caja_rem, base=manejo_caja_rem)
    if km_rem:
        _add(items, km_label or "Adicional por KM", rem=km_rem, base=km_rem)

    if nr1:
        _add(items, "No Rem (variable)", nr=nr1, base=nr1)
    if nr2:
        _add(items, "Suma Fija (NR)", nr=nr2, base=nr2)
    if a_cuenta:
        _add(items, "A cuenta de futuros aumentos", rem=a_cuenta, base=a_cuenta)
    if viaticos_nr:
        _add(items, "Viáticos (NR sin aportes)", nr=viaticos_nr, base=viaticos_nr)

    if pres_rem or pres_nr:
        _add(items, "Presentismo", rem=pres_rem, nr=pres_nr, base=base_pre + base_nr_pre)

    if hex50_rem or hex50_nr:
        _add(items, "Horas extra 50%", rem=hex50_rem, nr=hex50_nr, base=hora_rem)
    if hex100_rem or hex100_nr:
        _add(items, "Horas extra 100%", rem=hex100_rem, nr=hex100_nr, base=hora_rem)
    if noct_rem or noct_nr:
        _add(items, "Horas nocturnas (13,33%)", rem=noct_rem, nr=noct_nr, base=hora_rem)

    if fer_no_rem:
        _add(items, "Feriados no trabajados", rem=fer_no_rem, base=dia_rem_25)
    if fer_si_rem or fer_si_nr:
        _add(items, "Feriados trabajados", rem=fer_si_rem, nr=fer_si_nr, base=dia_rem_25)

    if vac_add_rem or vac_add_nr:
        _add(items, "Vacaciones gozadas (dif. 25/30)", rem=vac_add_rem, nr=vac_add_nr, base=base_pre)

    if lic_sg:
        _add(items, "Licencia sin goce / Suspensión (días)", ded=ded_lic, base=lic_sg)
    if aus:
        _add(items, "Ausencias injustificadas (días)", ded=ded_aus, base=aus)

    # Deducciones
    if jub: _add(items, "Jubilación (11%)", ded=jub, base=total_rem)
    if pami: _add(items, "Ley 19.032 (3%)", ded=pami, base=total_rem)
    if os_3: _add(items, "Obra Social (3%)", ded=os_3, base=base_ap)
    if os_100: _add(items, "Aporte fijo OSECAC", ded=os_100, base=os_100)
    if faecys: _add(items, "FAECYS (0,5%)", ded=faecys, base=base_ap)
    if sind_solid: _add(items, "Sindicato 2% Art 100", ded=sind_solid, base=base_ap)
    if afil_pct: _add(items, f"Sindicato Afiliación {_fmt_pct(sind_pct)}%", ded=afil_pct, base=base_ap)
    if afil_fijo: _add(items, "Sindicato Afiliación", ded=afil_fijo, base=base_ap)
    if faltante: _add(items, "Faltante de caja", ded=faltante, base=faltante)
    if embargo: _add(items, "Embargo", ded=embargo, base=embargo)

    return {
        "ok": True,
        "modo": "MENSUAL",
        "items": items,
        "totales": {
            "remunerativo": _r2(total_rem),
            "no_remunerativo": _r2(total_nr),
            "deducciones": _r2(total_ded),
            "neto": _r2(neto),

            # compat HTML
            "rem": _r2(total_rem),
            "nr": _r2(total_nr),
            "ind": _r2(0.0),
            "ded": _r2(total_ded),
        },
    }


def _calcular_final(p: Dict[str, Any]) -> Dict[str, Any]:
    """Liquidación final (Renuncia / Despido con o sin causa).

    Devuelve compat con el HTML:
      - items: concepto + columnas r/n/i/d
      - totales: rem/nr/ind/ded/neto

    Criterio:
      - Indemnización Art. 245 -> indemnizatorio (i) y NO integra base de aportes.
      - Preaviso e Integración -> remunerativo (r).
      - Vacaciones no gozadas y SAC proporcionales -> remunerativo (r).
      - Base (MEJOR SALARIO) se toma desde lf_mrmnh si viene; si no, se aproxima.
    """

    rama = p.get('rama')
    mes = p.get('mes')
    hs = _f(p.get('hs') or 48) or 48
    hs = max(1.0, min(48.0, hs))
    anios = int(_f(p.get('anios') or 0) or 0)

    ingreso = _parse_date(p.get('lf_ingreso'))
    egreso = _parse_date(p.get('lf_egreso'))
    if not ingreso or not egreso:
        return {"ok": False, "error": "Liquidación final: faltan lf_ingreso / lf_egreso"}

    # Base indemnizatoria / mejor salario (incluye NR según política del sistema)
    mrmnh = _f(p.get('lf_mrmnh') or 0)
    if mrmnh <= 0:
        row = find_row(p.get('rama'), p.get('agrup') or '—', p.get('categoria'), p.get('mes'))
        if row:
            basico = _f(row.get('basico') or 0.0)
            nr = _f(row.get('no_rem', 0)) + _f(row.get('suma_fija', 0))
            factor_hs = 1.0
            if not _is_call(rama):
                factor_hs = hs / 48.0
            basico *= factor_hs
            nr *= factor_hs
            ant_fac = _ant_factor(rama, anios)
            mrmnh = (basico + nr) + (basico * ant_fac) + (nr * ant_fac)
        else:
            mrmnh = 0.0

    # Días del mes de egreso
    first = egreso.replace(day=1)
    last = (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    dias_mes = last.day
    dias_trab = egreso.day

    dia_30 = mrmnh / 30.0 if mrmnh else 0.0
    dias_trab_total = dia_30 * dias_trab

    # Vacaciones proporcionales
    vac_anuales = _vac_anuales_por_antig(anios)
    dias_anno = (egreso - dt.date(egreso.year, 1, 1)).days + 1
    vac_prop = (vac_anuales * dias_anno) / 365.0
    vac_dias = int(vac_prop)  # piso
    vac_total = (mrmnh / 25.0) * vac_dias if (vac_dias and mrmnh) else 0.0

    # SAC proporcional
    sem_start = dt.date(egreso.year, 1, 1) if egreso.month <= 6 else dt.date(egreso.year, 7, 1)
    dias_sem = (egreso - sem_start).days + 1
    sac_prop = (mrmnh / 12.0) * (dias_sem / 182.5) if mrmnh else 0.0

    tipo = _u(p.get('lf_tipo') or 'RENUNCIA')
    ind245 = 0.0
    anios_indemn = 0
    if tipo in ('DESPIDO_SIN_CAUSA', 'DESPIDO SIN CAUSA'):
        anios_indemn = max(1, anios)
        ind245 = mrmnh * anios_indemn if mrmnh else 0.0

    preav_dias = int(_f(p.get('lf_preaviso') or 0) or 0)
    preav = dia_30 * preav_dias if preav_dias else 0.0
    sac_pre = (preav / 12.0) if (preav and bool(p.get('lf_sac_pre'))) else 0.0

    integ = bool(p.get('lf_integracion'))
    integ_dias = (dias_mes - egreso.day) if integ else 0
    integ_total = dia_30 * integ_dias if integ_dias else 0.0
    sac_int = (integ_total / 12.0) if (integ_total and bool(p.get('lf_sac_int'))) else 0.0

    items: List[Dict[str, Any]] = []
    _add(items, f"Días trabajados ({dias_trab})", rem=dias_trab_total)
    if vac_dias:
        _add(items, f"Vacaciones no gozadas ({vac_dias})", rem=vac_total)
    if sac_prop:
        _add(items, 'SAC proporcional', rem=sac_prop)

    if ind245:
        _add(items, 'Indemnización Art. 245', ind=ind245)

    if preav:
        _add(items, f"Preaviso ({preav_dias} días)", rem=preav)
        if sac_pre:
            _add(items, 'SAC s/ Preaviso', rem=sac_pre)

    if integ_total:
        _add(items, f"Integración mes despido ({integ_dias} días)", rem=integ_total)
        if sac_int:
            _add(items, 'SAC s/ Integración', rem=sac_int)

    # Totales antes de deducciones
    total_rem = sum(it.get('r', 0.0) for it in items)
    total_nr = sum(it.get('n', 0.0) for it in items)
    total_ind = sum(it.get('i', 0.0) for it in items)

    # Deducciones (mismas reglas):
    # - Jubilación/PAMI solo sobre Remunerativo
    # - OSECAC/FAECYS/Sindicato sobre Rem + NR (sin viáticos)
    jubilado = bool(p.get('jubilado'))
    afiliado = bool(p.get('afiliado'))
    osecac = bool(p.get('osecac', True))

    sind_pct = _f(p.get('sind_pct') or 0) or 0.0
    sind_fijo = _f(p.get('sind_fijo') or 0) or 0.0

    viaticos_nr = _f(p.get('viaticos_nr') or 0)
    base_ap = _base_aportes(total_rem, total_nr, viaticos_nr)

    jub = total_rem * 0.11
    pami = 0.0 if jubilado else total_rem * 0.03
    os_3 = (base_ap * 0.03) if (osecac and not jubilado) else 0.0
    os_100 = 100.0 if (osecac and not jubilado) else 0.0
    faecys = base_ap * 0.005
    sind_solid = base_ap * 0.02
    afil_pct = base_ap * (sind_pct / 100.0) if (afiliado and sind_pct > 0) else 0.0
    afil_fijo = sind_fijo if (afiliado and sind_fijo > 0) else 0.0

    if jub:
        _add(items, 'Jubilación (11%)', ded=jub, base=total_rem)
    if pami:
        _add(items, 'Ley 19.032 (3%)', ded=pami, base=total_rem)
    if os_3:
        _add(items, 'Obra Social (3%)', ded=os_3, base=base_ap)
    if os_100:
        _add(items, 'Aporte fijo OSECAC', ded=os_100, base=os_100)
    if faecys:
        _add(items, 'FAECYS (0,5%)', ded=faecys, base=base_ap)
    if sind_solid:
        _add(items, 'Sindicato 2% Art 100', ded=sind_solid, base=base_ap)
    if afil_pct:
        _add(items, f'Sindicato Afiliación {_fmt_pct(sind_pct)}%', ded=afil_pct, base=base_ap)
    if afil_fijo:
        _add(items, 'Sindicato Afiliación', ded=afil_fijo, base=base_ap)

    total_ded = jub + pami + os_3 + os_100 + faecys + sind_solid + afil_pct + afil_fijo
    neto = (total_rem + total_nr + total_ind) - total_ded

    return {
        'ok': True,
        'modo': 'FINAL',
        'base_indemnizatoria': _r2(mrmnh),
        'anios_indemn': int(anios_indemn),
        'items': items,
        'totales': {
            'remunerativo': _r2(total_rem),
            'no_remunerativo': _r2(total_nr),
            'indemnizatorio': _r2(total_ind),
            'deducciones': _r2(total_ded),
            'neto': _r2(neto),

            # compat HTML
            'rem': _r2(total_rem),
            'nr': _r2(total_nr),
            'ind': _r2(total_ind),
            'ded': _r2(total_ded),
        },
    }


# -----------------
# Wrappers (compat con el HTML)
# -----------------

def _norm(s: Any) -> str:
    return str(s or "").strip()


def _u2(s: Any) -> str:
    return _norm(s).upper()


def _b(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v or "").strip().lower()
    return s in ("1", "true", "si", "sí", "s", "on", "yes")


def _mes_key(v: Any) -> str:
    if isinstance(v, (dt.date, dt.datetime)):
        return v.strftime("%Y-%m")
    s = _norm(v)
    if len(s) >= 7 and s[4] == "-":
        return s[:7]
    return s


def calcular_mensual_desde_query(qp: Dict[str, Any]) -> Dict[str, Any]:
    rama = _u2(qp.get("rama"))
    mes = _mes_key(qp.get("mes"))
    if not rama or not mes:
        return {"ok": False, "error": "Faltan parametros: rama y mes"}

    agrup = _norm(qp.get("agrup") or "—")
    categoria = _norm(qp.get("categoria") or "—")

    hs = _f(qp.get("jornada") or qp.get("hs") or 48)
    anios = _f(qp.get("anios_antig") or qp.get("anios") or 0)
    zona_pct = _f(qp.get("zona") or qp.get("zona_pct") or 0)

    # turismo titulo
    tur_titulo_pct = _f(qp.get("titulo_pct") or 0)
    if not tur_titulo_pct:
        tur_titulo_pct = float(escalas.get_titulo_pct_por_nivel(_norm(qp.get("tituloNivel"))))

    # agua conexiones
    agua_conex = int(_f(qp.get("conex") or qp.get("agua_conex") or 0) or 0)

    payload: Dict[str, Any] = {
        "modo": "MENSUAL",
        "rama": rama,
        "agrup": agrup,
        "categoria": categoria,
        "mes": mes,
        "hs": hs,
        "anios": anios,
        "zona_pct": zona_pct,
        "presentismo": _b(qp.get("presentismo", True)),
        "tur_titulo_pct": tur_titulo_pct,
        "agua_conex": agua_conex,
        "armado_vidriera": _b(qp.get("armadoAuto") or qp.get("armado_vidriera")),
        "manejo_caja": _b(qp.get("manejoCaja") or qp.get("manejo_caja")),
        "cajero_tipo": _norm(qp.get("cajero_tipo") or qp.get("cajeroTipo") or qp.get("cajero_tipo2")),
        "km_tipo": _norm(qp.get("kmTipo") or qp.get("km_tipo")),
        "km_menos100": _f(qp.get("kmMenos100") or qp.get("km_menos100") or 0),
        "km_mas100": _f(qp.get("kmMas100") or qp.get("km_mas100") or 0),
        "a_cuenta": _f(qp.get("aCuentaNR") or qp.get("a_cuenta") or 0),
        "viaticos_nr": _f(qp.get("viaticosNR") or qp.get("viaticos_nr") or 0),
        "hex50": _f(qp.get("hex50") or 0),
        "hex100": _f(qp.get("hex100") or 0),
        "noct": _f(qp.get("noct") or qp.get("nocturnas") or 0),
        "fer_si": _f(qp.get("ferTrab") or qp.get("fer_si") or 0),
        "fer_no": _f(qp.get("ferNoTrab") or qp.get("fer_no") or 0),
        "vac_goz": _f(qp.get("vacGoz") or qp.get("vac_goz") or 0),
        "lic_sg": _f(qp.get("licSG") or qp.get("lic_sg") or 0),
        "aus": _f(qp.get("aus") or 0),
        "faltante": _f(qp.get("faltante") or 0),
        "embargo": _f(qp.get("embargo") or 0) + _f(qp.get("adelanto") or qp.get("adelantoSueldo") or 0),
        "jubilado": _b(qp.get("jubilado")),
        "afiliado": _b(qp.get("afiliado")),
        "osecac": _b(qp.get("osecac", True)),
    }

    # flags fúnebres (funAdic1..N)
    for k, v in qp.items():
        if str(k).startswith("funAdic"):
            payload[str(k)] = v

    return calcular_recibo(payload)


def calcular_final_desde_query(qp: Dict[str, Any]) -> Dict[str, Any]:
    # Para final usamos el mismo motor interno (_calcular_final)
    payload: Dict[str, Any] = {
        "modo": "FINAL",
        "lf_ingreso": _norm(qp.get("ingreso") or qp.get("alta") or qp.get("lf_ingreso")),
        "lf_egreso": _norm(qp.get("egreso") or qp.get("baja") or qp.get("lf_egreso")),
        "lf_tipo": _norm(qp.get("tipo") or qp.get("causal") or qp.get("lf_tipo") or "RENUNCIA"),
        "lf_mrmnh": _f(qp.get("mejor_salario") or qp.get("lf_mrmnh") or 0),
        "lf_preaviso": _f(qp.get("preaviso") or qp.get("lf_preaviso") or 0),
        "lf_sac_pre": _b(qp.get("sac_preaviso") or qp.get("lf_sac_pre")),
        "lf_integracion": _b(qp.get("integracion") or qp.get("lf_integracion")),
        "lf_sac_int": _b(qp.get("sac_integracion") or qp.get("lf_sac_int")),
        "jubilado": _b(qp.get("jubilado")),
        "afiliado": _b(qp.get("afiliado")),
        "osecac": _b(qp.get("osecac", True)),
        "viaticos_nr": _f(qp.get("viaticosNR") or qp.get("viaticos_nr") or 0),
    }

    # compat: si mandan rama/mes/categoria, se guardan (no son obligatorios para final)
    for k in ("rama", "agrup", "categoria", "mes"):
        if k in qp:
            payload[k] = qp.get(k)

    return calcular_recibo(payload)
