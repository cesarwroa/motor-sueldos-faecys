from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import datetime as dt
import math

import pandas as pd

from escalas import MAESTRO_PATH, find_row


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


def _vac_anuales_por_antig(anios: int) -> int:
    if anios < 5:
        return 14
    if anios < 10:
        return 21
    if anios < 20:
        return 28
    return 35


def _load_sheet(name: str) -> pd.DataFrame:
    try:
        return pd.read_excel(MAESTRO_PATH, sheet_name=name, engine="openpyxl")
    except Exception:
        return pd.DataFrame()


def _funebres_adicionales(mes: str, flags: Dict[str, Any]) -> float:
    df = _load_sheet("Adicionales")
    if df.empty:
        return 0.0

    def v(concepto: str) -> float:
        x = df[(df.get("Mes") == mes) & (df.get("Concepto") == concepto)]
        if x.empty:
            return 0.0
        return _f(x.iloc[0].get("Valor"))

    total = 0.0
    if bool(flags.get("funAdic1")):
        total += v("Adicional General (todo el personal, incluidos choferes)")
    if bool(flags.get("funAdic2")):
        total += v("Adicional Personal no incluido en inciso 1")
    if bool(flags.get("funAdic3")):
        total += v("Adicional Chofer/Furgonero (vehículos)")
    if bool(flags.get("funAdic4")):
        total += v("Adicional por Indumentaria")
    return total


def _conex_pct(conex: int) -> float:
    df = _load_sheet("ReglasConexiones")
    if df.empty or conex <= 0:
        return 0.0

    for _, r in df.iterrows():
        det = str(r.get("Detalle") or "").lower()
        pct = _f(r.get("Porcentaje"))
        # "0 a 200 conexiones"
        import re
        m = re.search(r"(\d+)\s*a\s*(\d+)\s*conex", det)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= conex <= b:
                return pct
        m = re.search(r"a\s*partir\s*de\s*(\d+)\s*conex", det)
        if m:
            a = int(m.group(1))
            if conex >= a:
                return pct
    return 0.0


def _ant_factor(rama: str, anios: int) -> float:
    if anios <= 0:
        return 0.0
    if _is_agua(rama):
        # 2% acumulativo
        return (math.pow(1.02, anios) - 1.0)
    return 0.01 * anios


def _base_aportes(rem: float, nr: float, viaticos_nr: float) -> float:
    # Viáticos NR se excluyen de aportes
    return max(0.0, (rem + nr) - viaticos_nr)


def _add(items: List[Dict[str, Any]], concepto: str, rem=0.0, nr=0.0, ded=0.0, base=0.0):
    items.append({
        "concepto": concepto,
        "base": _r2(base if base else (rem or nr or ded)),
        "remunerativo": _r2(rem),
        "no_remunerativo": _r2(nr),
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

    basico = _f(row["basico"])
    nr1 = _f(row["no_rem_1"])
    nr2 = _f(row["no_rem_2"])
    nr_base = nr1 + nr2

    # Prorrateo por hs: Call Center y Menores Cereales NO
    factor_hs = 1.0
    if not _is_call(rama) and not (_is_cereales(rama) and "MENORES" in _u(categoria)):
        factor_hs = hs / 48.0

    basico *= factor_hs
    nr_base *= factor_hs
    nr1 *= factor_hs
    nr2 *= factor_hs

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
    base_pre = basico + ant_rem + zona_rem + a_cuenta + tit_rem + conex_rem + fun_rem
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
    noct_rem = hora_rem * 0.3 * noct
    noct_nr = hora_nr * 0.3 * noct

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

    base_ap = _base_aportes(total_rem, total_nr, viaticos_nr)

    jub = 0.0 if jubilado else total_rem * 0.11
    pami = 0.0 if jubilado else total_rem * 0.03

    os_3 = 0.0
    os_100 = 0.0
    if osecac and (not jubilado):
        os_3 = base_ap * 0.03
        os_100 = 100.0

    faecys = base_ap * 0.005
    sind_solid = base_ap * 0.02
    sind_af = base_ap * 0.02 if afiliado else 0.0

    total_ded = jub + pami + os_3 + os_100 + faecys + sind_solid + sind_af + ded_lic + ded_aus + faltante + embargo
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
        _add(items, "Horas nocturnas (30%)", rem=noct_rem, nr=noct_nr, base=hora_rem)

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
    if sind_solid: _add(items, "Sindicato (2%)", ded=sind_solid, base=base_ap)
    if sind_af: _add(items, "Afiliación (2%)", ded=sind_af, base=base_ap)
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
        },
    }


def _calcular_final(p: Dict[str, Any]) -> Dict[str, Any]:
    # Insumos
    rama = p.get("rama")
    mes = p.get("mes")
    hs = _f(p.get("hs") or 48) or 48
    hs = max(1.0, min(48.0, hs))
    anios = int(_f(p.get("anios") or 0) or 0)

    ingreso = _parse_date(p.get("lf_ingreso"))
    egreso = _parse_date(p.get("lf_egreso"))
    if not ingreso or not egreso:
        return {"ok": False, "error": "Liquidación final: faltan lf_ingreso / lf_egreso"}

    # Para base mensual, el front debe enviar mrmnh si quiere (si no, lo aproximamos con basico del mes elegido)
    mrmnh = _f(p.get("lf_mrmnh") or 0)
    if mrmnh <= 0:
        # aproximación: usar el básico del mes elegido (si hay)
        row = find_row(p.get("rama"), p.get("agrup") or "—", p.get("categoria"), p.get("mes"))
        if row:
            basico = _f(row["basico"])
            nr = _f(row["no_rem_1"]) + _f(row["no_rem_2"])
            factor_hs = 1.0
            if not _is_call(rama):
                factor_hs = hs / 48.0
            basico *= factor_hs
            nr *= factor_hs
            ant_fac = _ant_factor(rama, anios)
            mrmnh = (basico + nr) + (basico * ant_fac) + (nr * ant_fac)
        else:
            mrmnh = 0.0

    # días mes egreso
    first = egreso.replace(day=1)
    last = (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    dias_mes = last.day
    dias_trab = egreso.day

    # base diaria 30
    dia_30 = mrmnh / 30.0 if mrmnh else 0.0
    dias_trab_total = dia_30 * dias_trab

    # Vacaciones proporcionales
    vac_anuales = _vac_anuales_por_antig(anios)
    dias_anno = (egreso - dt.date(egreso.year, 1, 1)).days + 1
    vac_prop = (vac_anuales * dias_anno) / 365.0
    vac_dias = math.floor(vac_prop + 1e-9)
    vac_total = (mrmnh / 25.0) * vac_dias if vac_dias else 0.0

    # SAC proporcional (simple)
    sem_start = dt.date(egreso.year, 1, 1) if egreso.month <= 6 else dt.date(egreso.year, 7, 1)
    dias_sem = (egreso - sem_start).days + 1
    sac_prop = (mrmnh / 12.0) * (dias_sem / 182.5)

    tipo = _u(p.get("lf_tipo") or "RENUNCIA")
    ind245 = 0.0
    if tipo in ("DESPIDO_SIN_CAUSA", "DESPIDO SIN CAUSA"):
        ind245 = mrmnh * max(1, anios)

    preav_dias = int(_f(p.get("lf_preaviso") or 0) or 0)
    preav = dia_30 * preav_dias if preav_dias else 0.0
    sac_pre = (preav / 12.0) if bool(p.get("lf_sac_pre")) else 0.0

    integ = bool(p.get("lf_integracion"))
    integ_dias = (dias_mes - egreso.day) if integ else 0
    integ_total = dia_30 * integ_dias if integ_dias else 0.0
    sac_int = (integ_total / 12.0) if bool(p.get("lf_sac_int")) else 0.0

    items: List[Dict[str, Any]] = []
    _add(items, f"Días trabajados ({dias_trab})", rem=dias_trab_total)
    if vac_dias:
        _add(items, f"Vacaciones no gozadas ({vac_dias})", rem=vac_total)
    _add(items, "SAC proporcional", rem=sac_prop)
    if ind245:
        _add(items, "Indemnización Art. 245", rem=ind245)
    if preav:
        _add(items, f"Preaviso ({preav_dias} días)", rem=preav)
        if sac_pre:
            _add(items, "SAC s/ Preaviso", rem=sac_pre)
    if integ_total:
        _add(items, f"Integración mes despido ({integ_dias} días)", rem=integ_total)
        if sac_int:
            _add(items, "SAC s/ Integración", rem=sac_int)

    total_rem = sum(i["remunerativo"] for i in items)
    total_nr = 0.0

    # Deducciones (mismas reglas)
    jubilado = bool(p.get("jubilado"))
    afiliado = bool(p.get("afiliado"))
    osecac = bool(p.get("osecac", True))

    viaticos_nr = _f(p.get("viaticos_nr") or 0)
    base_ap = _base_aportes(total_rem, total_nr, viaticos_nr)

    jub = 0.0 if jubilado else total_rem * 0.11
    pami = 0.0 if jubilado else total_rem * 0.03
    os_3 = (base_ap * 0.03) if (osecac and not jubilado) else 0.0
    os_100 = 100.0 if (osecac and not jubilado) else 0.0
    faecys = base_ap * 0.005
    sind_solid = base_ap * 0.02
    sind_af = base_ap * 0.02 if afiliado else 0.0

    if jub: _add(items, "Jubilación (11%)", ded=jub, base=total_rem)
    if pami: _add(items, "Ley 19.032 (3%)", ded=pami, base=total_rem)
    if os_3: _add(items, "Obra Social (3%)", ded=os_3, base=base_ap)
    if os_100: _add(items, "Aporte fijo OSECAC", ded=os_100, base=os_100)
    if faecys: _add(items, "FAECYS (0,5%)", ded=faecys, base=base_ap)
    if sind_solid: _add(items, "Sindicato (2%)", ded=sind_solid, base=base_ap)
    if sind_af: _add(items, "Afiliación (2%)", ded=sind_af, base=base_ap)

    total_ded = jub + pami + os_3 + os_100 + faecys + sind_solid + sind_af
    neto = (total_rem + total_nr) - total_ded

    return {
        "ok": True,
        "modo": "FINAL",
        "items": items,
        "totales": {
            "remunerativo": _r2(total_rem),
            "no_remunerativo": _r2(total_nr),
            "deducciones": _r2(total_ded),
            "neto": _r2(neto),
        },
    }
