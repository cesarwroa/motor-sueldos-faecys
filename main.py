from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException

from models import DatosEmpleado
from escalas import buscar_escala, valor_funebres, ESCALAS, _norm


app = FastAPI(title="ComercioOnline - Cálculo CCT 130/75")


def r2(x: float) -> float:
    # JS: Math.round(x*100)/100
    return round(float(x or 0.0), 2)


def pf(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(".", "").replace(",", ".") if ("," in str(v) and "." in str(v)) else str(v).strip().replace(",", ".")
        return float(s) if s else 0.0
    except Exception:
        return 0.0


def hs_from_categoria_text(cat: str) -> Optional[float]:
    import re
    m = re.search(r"([0-9]+)\s*HS", cat or "", flags=re.I)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def is_menores(rama: str, categoria: str) -> bool:
    rk = _norm(rama)
    ck = _norm(categoria)
    return ck.startswith("MENORES") or (rk == "CEREALES" and "MENOR" in ck)


def calcular_factor_agua_potable(anios: float) -> float:
    # Replica la idea de "2% acumulativo por año": (1.02^anios - 1)
    a = max(0.0, float(anios or 0.0))
    return (1.02 ** a) - 1.0


def buscar_basico_inicial_global_por_nombre(mes: str, nombre_exacto: str) -> float:
    n = _norm(nombre_exacto)
    for row in ESCALAS:
        if row.get("Mes", "").strip() != (mes or "").strip():
            continue
        if _norm(row.get("Rama", "")) != "GENERAL":
            continue
        if _norm(row.get("Categoria", "")) == n:
            return pf(row.get("Basico"))
    return 0.0


def buscar_basico_inicial_caj(mes: str, letra: str) -> float:
    # JS: buscarBasicoInicialCaj('GENERAL','(TODAS)', mes, letra === 'B' ? 'B' : 'A')
    # Implementación: intenta matchear categorías de cajeros por letra en GENERAL.
    letra = (letra or "").strip().upper() or "A"
    target = "CAJERO"  # la categoría suele contener CAJEROS / CAJERO
    for row in ESCALAS:
        if row.get("Mes", "").strip() != (mes or "").strip():
            continue
        if _norm(row.get("Rama", "")) != "GENERAL":
            continue
        cat = _norm(row.get("Categoria", ""))
        if target in cat and f" {letra}" in cat:
            return pf(row.get("Basico"))
    # fallback: si no encuentra por letra, intenta "CAJEROS A" como base
    for row in ESCALAS:
        if row.get("Mes", "").strip() != (mes or "").strip():
            continue
        if _norm(row.get("Rama", "")) != "GENERAL":
            continue
        cat = _norm(row.get("Categoria", ""))
        if target in cat and " A" in cat:
            return pf(row.get("Basico"))
    return 0.0


@dataclass
class Item:
    concepto: str
    remunerativo: float = 0.0
    no_remunerativo: float = 0.0
    deduccion: float = 0.0
    base: Optional[float] = None


def calcular_sueldo(d: DatosEmpleado) -> Dict[str, Any]:
    # 1) Traer escala (igual que JS: basico/nrVar/nrSF vienen del maestro según selectores)
    row = buscar_escala(d.rama, d.agrup, d.categoria, d.mes)
    if not row:
        raise HTTPException(status_code=400, detail="No se encontró escala para Rama/Agrup/Categoría/Mes.")

    basico_raw = pf(row.get("Basico"))
    nr_var_raw = pf(row.get("NRVar") if "NRVar" in row else row.get("NoRemVar") if "NoRemVar" in row else row.get("NR") if "NR" in row else row.get("NoRem") )
    nr_sf_raw  = pf(row.get("NRSF") if "NRSF" in row else row.get("SumaFija") if "SumaFija" in row else row.get("NoRemSF") )

    # 2) Horas
    hs_in = pf(d.hs)
    hs_cat = hs_from_categoria_text(d.categoria) or 48.0
    if (not hs_in) or (hs_in > hs_cat):
        hs_in = hs_cat
    if is_menores(d.rama, d.categoria):
        hs_in = 48.0  # JS: no prorratear menores
    hs = min(48.0, max(1.0, hs_in))
    prop = hs / 48.0

    # 3) Prorrateo de básicos/NR
    if _norm(d.rama) == "CALL CENTER":
        basico = basico_raw
        nr_var = nr_var_raw
        nr_sf  = nr_sf_raw
    else:
        basico = basico_raw * prop
        nr_var = nr_var_raw * prop
        nr_sf  = nr_sf_raw * prop

    a_cuenta = pf(d.aCuentaNR)
    viaticos_nr = pf(d.viaticosNR)
    nr_base = nr_var + nr_sf

    # 4) Antigüedad
    if _norm(d.rama) == "AGUA POTABLE":
        factor = calcular_factor_agua_potable(d.anios)
        adic_ant_rem = basico * factor
        adic_ant_nr  = nr_base * factor
    else:
        adic_ant_rem = basico * 0.01 * pf(d.anios)
        adic_ant_nr  = nr_base * 0.01 * pf(d.anios)

    # 5) Zona (solo Rem en el JS)
    zona_pc = pf(d.zona)
    zona_rem = (basico + adic_ant_rem) * (zona_pc / 100.0)
    zona_nr = 0.0

    # 6) Hora normal / HE (divisor 200)
    hora_normal_rem = basico / 200.0
    hora_normal_nr  = nr_base / 200.0
    hex50_rem = hora_normal_rem * 1.5 * pf(d.hex50)
    hex50_nr  = hora_normal_nr  * 1.5 * pf(d.hex50)
    hex100_rem = hora_normal_rem * 2.0 * pf(d.hex100)
    hex100_nr  = hora_normal_nr  * 2.0 * pf(d.hex100)

    # 7) Nocturnidad (30% x hora normal x hsNoct)
    noct_rem = hora_normal_rem * 0.3 * pf(d.hsNoct)
    noct_nr  = hora_normal_nr  * 0.3 * pf(d.hsNoct)

    # 8) Feriados (día = (Básico + Antig + Zona)/30; NR día = (NRBase + AntNR)/30)
    base_fer_rem = (basico + adic_ant_rem + zona_rem)
    base_fer_nr  = (nr_base + adic_ant_nr)
    valor_dia_rem = base_fer_rem / 30.0
    valor_dia_nr  = base_fer_nr  / 30.0
    fer_no_rem = valor_dia_rem * pf(d.ferNoTrab)
    fer_no_nr  = valor_dia_nr  * pf(d.ferNoTrab)
    fer_si_rem = valor_dia_rem * 2.0 * pf(d.ferTrab)
    fer_si_nr  = valor_dia_nr  * 2.0 * pf(d.ferTrab)

    # 9) Vacaciones gozadas (1/25) + licencia paga no altera; licencia sin goce descuenta luego (1/30)
    vac_dias = pf(d.coVacDias)
    vdia_rem_plus = base_fer_rem / 25.0
    vdia_nr_plus  = base_fer_nr  / 25.0
    vac_rem = r2(vac_dias * vdia_rem_plus)
    vac_nr  = r2(vac_dias * vdia_nr_plus)

    # 10) Manejo de caja (NO Rem) según JS: (baseLetra * pct)/12
    manejo_caja_nr = 0.0
    if d.manejoCaja:
        letra = (d.cajero_tipo or "").strip().upper()
        if not letra:
            cU = _norm(d.categoria)
            import re
            if re.search(r"CAJER\w*\s*B\b", cU):
                letra = "B"
            elif re.search(r"CAJER\w*\s*C\b", cU):
                letra = "C"
            else:
                letra = "A"
        pct = 0.48 if letra == "B" else 0.1225
        base_letra = buscar_basico_inicial_caj(d.mes, "B" if letra == "B" else "A")
        manejo_caja_nr = (base_letra * pct) / 12.0

    # 11) Adicionales Fúnebres (Rem, luego * prop según JS)
    fun_rem = 0.0
    if _norm(d.rama) in ("FÚNEBRES", "FUNEBRES"):
        v_gen = valor_funebres("CADAVER", d.mes)
        v_res = valor_funebres("RESTO", d.mes)
        v_cho = valor_funebres("CHOFER", d.mes)
        v_ind = valor_funebres("INDUMENT", d.mes)
        if d.funAdic1:
            fun_rem += v_gen
        if d.funAdic2:
            fun_rem += v_res
        if d.funAdic3:
            fun_rem += v_cho
            if not d.funAdic1:
                fun_rem += v_gen
        if d.funAdic4:
            fun_rem += v_ind
        fun_rem *= prop

    fun_nr = 0.0  # JS: ya no usa NR para fúnebres

    # 12) Vidrierista (Armado de vidriera): base Vendedor B * 0.0383
    vidriera_rem = 0.0
    if d.armadoAuto:
        base_vb = buscar_basico_inicial_global_por_nombre(d.mes, "VENDEDOR B")
        if base_vb <= 0:
            base_vb = buscar_basico_inicial_global_por_nombre(d.mes, "VENDEDOR  B")
        vidriera_rem = base_vb * 0.0383
        # (en el JS este adicional no se prorratea por jornada)

    # 13) Totales base para presentismo (Rem + NR)  (sin presentismo)
    # Nota: aCuentaNR se suma a Rem (como en el JS: totalRemBase incluye aCuenta)
    base_rem_mensual = basico + adic_ant_rem + zona_rem + hex50_rem + hex100_rem + noct_rem + fer_no_rem + fer_si_rem + vac_rem + fun_rem + vidriera_rem + a_cuenta
    base_nr_mensual  = nr_base + adic_ant_nr + zona_nr + hex50_nr + hex100_nr + noct_nr + fer_no_nr + fer_si_nr + vac_nr

    total_rem_base = base_rem_mensual
    total_nr_base  = base_nr_mensual

    # Exponer bases como en JS (solo si querés debug)
    base_pres_rem = total_rem_base
    base_pres_nr  = total_nr_base

    pres_ok = pf(d.coAus) <= 1.0
    pres_rem = (total_rem_base / 12.0) if pres_ok else 0.0
    pres_nr  = (total_nr_base  / 12.0) if pres_ok else 0.0

    total_rem = total_rem_base + pres_rem
    total_nr  = total_nr_base + pres_nr + manejo_caja_nr + viaticos_nr

    # 14) SAC junio/diciembre
    mes_num = int((d.mes.split("-")[1] if d.mes and "-" in d.mes else "0") or "0")
    sac_rem = 0.0
    sac_nr = 0.0
    if mes_num in (6, 12):
        base_sac_rem = base_rem_mensual + pres_rem
        base_sac_nr  = base_nr_mensual  + pres_nr
        sac_rem = r2(base_sac_rem * 0.5)
        sac_nr  = r2(base_sac_nr  * 0.5)
        total_rem += sac_rem
        total_nr  += sac_nr

    # 15) Licencia sin goce (descuento 1/30 sobre totalRem)
    total_rem_ajust = total_rem
    desc_lic = 0.0
    if d.coLicS and d.coLicS > 0:
        v_dia_lic = total_rem / 30.0
        desc_lic = r2(v_dia_lic * float(d.coLicS))
        total_rem_ajust = r2(total_rem - desc_lic)

    # 16) Deducciones
    es_jubilado = bool(d.coJub)
    jubil = total_rem_ajust * 0.11
    pami  = 0.0 if es_jubilado else (total_rem * 0.03)

    # Base aportes: Rem + (NR - manejoCajaNR - funNR - viaticosNR)
    base_aportes = total_rem + (total_nr - manejo_caja_nr - fun_nr - viaticos_nr)
    faecys = base_aportes * 0.005
    sind_obl = base_aportes * 0.02
    # sindicato adicional (% selector + fijo)
    sel = (d.afiliado_selector or "NO").strip().upper()
    pct = 0.0 if sel == "NO" else pf(sel)
    sind_af = (pct / 100.0) * base_aportes + pf(d.afiliado_fijo)

    # Obra social: baseOS = totalRem + (NR - manejoCajaNR - viaticosNR) si OSECAC; y en CALL CENTER elevar a 48hs
    tiene_osecac = (d.osecac == "si")
    base_os_rem = total_rem
    base_os_nr = (total_nr - manejo_caja_nr - viaticos_nr) if tiene_osecac else 0.0
    base_os_total = base_os_rem + base_os_nr

    if _norm(d.rama) == "CALL CENTER":
        # elevar a 48hs según hsCat (20/24/30/36/48)
        if hs_cat > 0 and hs_cat < 48:
            base_os_total = base_os_total * 48.0 / hs_cat

    osecac_var = 0.0 if es_jubilado else (base_os_total * 0.03)
    osecac_fijo = 0.0 if es_jubilado else (100.0 if tiene_osecac else 0.0)

    total_ded = jubil + pami + faecys + sind_obl + sind_af + osecac_var + osecac_fijo
    neto = (total_rem + total_nr) - total_ded

    items: List[Item] = []

    def push(concepto: str, rem: float = 0.0, nr: float = 0.0, ded: float = 0.0, base: Optional[float] = None):
        items.append(Item(concepto=concepto, remunerativo=r2(rem), no_remunerativo=r2(nr), deduccion=r2(ded), base=base))

    # Conceptos base
    push("Básico", rem=basico, base=basico_raw if _norm(d.rama)!="CALL CENTER" else basico_raw)
    if adic_ant_rem or adic_ant_nr:
        push("Antigüedad", rem=adic_ant_rem, nr=adic_ant_nr, base=pf(d.anios))
    if zona_rem:
        push("Zona", rem=zona_rem, base=zona_pc)
    if a_cuenta:
        push("A cuenta NR", rem=a_cuenta)
    if nr_base:
        push("No Rem (base)", nr=nr_base)
    if hex50_rem or hex50_nr:
        push("Horas extra 50%", rem=hex50_rem, nr=hex50_nr)
    if hex100_rem or hex100_nr:
        push("Horas extra 100%", rem=hex100_rem, nr=hex100_nr)
    if noct_rem or noct_nr:
        push("Horas nocturnas (30%)", rem=noct_rem, nr=noct_nr)
    if fer_no_rem or fer_no_nr:
        push("Feriado no trabajado", rem=fer_no_rem, nr=fer_no_nr)
    if fer_si_rem or fer_si_nr:
        push("Feriado trabajado", rem=fer_si_rem, nr=fer_si_nr)
    if vac_rem or vac_nr:
        push("Vacaciones gozadas", rem=vac_rem, nr=vac_nr)
    if fun_rem:
        push("Adicionales Fúnebres", rem=fun_rem)
    if vidriera_rem:
        push("Armado de vidriera (3,83%)", rem=vidriera_rem)
    if manejo_caja_nr:
        push("Manejo de caja (NO Rem)", nr=manejo_caja_nr)
    if viaticos_nr:
        push("Viáticos (NO Rem)", nr=viaticos_nr)
    if pres_rem or pres_nr:
        push("Presentismo (1/12)", rem=pres_rem, nr=pres_nr, base=(base_pres_rem+base_pres_nr))
    if sac_rem or sac_nr:
        push("SAC (50%)", rem=sac_rem, nr=sac_nr)

    # Descuentos / deducciones
    if desc_lic:
        push("Licencia sin goce / Suspensión (días)", ded=desc_lic, base=d.coLicS)
    push("Jubilación 11%", ded=jubil, base=total_rem_ajust)
    if pami:
        push("Ley 19.032 (PAMI) 3%", ded=pami, base=total_rem)
    push("FAECYS 0,5%", ded=faecys, base=base_aportes)
    push("Sindicato 2%", ded=sind_obl, base=base_aportes)
    if sind_af:
        push("Afiliación (variable)", ded=sind_af, base=base_aportes)
    if osecac_var:
        push("Obra Social 3%", ded=osecac_var, base=base_os_total)
    if osecac_fijo:
        push("OSECAC $100", ded=osecac_fijo)

    return {
        "inputs_normalizados": {
            "rama": d.rama,
            "agrup": d.agrup,
            "categoria": d.categoria,
            "mes": d.mes,
            "hs": hs,
            "hs_cat": hs_cat,
            "prop": prop,
            "pres_ok": pres_ok,
        },
        "totales": {
            "total_rem": r2(total_rem),
            "total_nr": r2(total_nr),
            "total_deducciones": r2(total_ded),
            "neto": r2(neto),
        },
        "items": [item.__dict__ for item in items],
    }


@app.post("/calcular")
def api_calcular(d: DatosEmpleado) -> Dict[str, Any]:
    return calcular_sueldo(d)
