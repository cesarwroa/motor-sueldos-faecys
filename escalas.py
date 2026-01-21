# -*- coding: utf-8 -*-
"""
escalas.py (sin pandas)
Lee el maestro Excel con openpyxl y expone helpers para:
- /meta (ramas, meses, agrupamientos, categorias)
- /payload (básico / no_rem / suma_fija)
- reglas: conexiones Agua Potable, adicionales Fúnebres, título Turismo, cajero, KM
"""
from __future__ import annotations

import os
import datetime as _dt
from functools import lru_cache
from typing import Dict, Tuple, List, Any, Optional

from decimal import Decimal, ROUND_HALF_UP

import openpyxl


# ---------------------------
# Config
# ---------------------------

def _default_maestro_path() -> str:
    # Preferimos SIEMPRE data/maestro_actualizado.xlsx (evita conflicto con un maestro en raíz).
    # Resolvemos relativo a este archivo, no al CWD, para evitar errores 500 en deploy.
    here = os.path.dirname(__file__)

    p1 = os.path.join(here, "data", "maestro_actualizado.xlsx")
    if os.path.exists(p1):
        return p1

    p2 = os.path.join(here, "data", "maestro.xlsx")
    if os.path.exists(p2):
        return p2

    # último fallback (raíz del proyecto)
    p3 = os.path.join(here, "maestro.xlsx")
    if os.path.exists(p3):
        return p3

    return "maestro.xlsx"


MAESTRO_PATH = os.getenv("MAESTRO_PATH", _default_maestro_path())


def round2(x: float) -> float:
    """Redondeo a 2 decimales (half up) para importes."""
    try:
        return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except Exception:
        return 0.0


# ---------------------------
# Utils
# ---------------------------

def _mes_to_key(v: Any) -> str:
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.strftime("%Y-%m")
    if v is None:
        return ""
    s = str(v).strip()
    # admite "2026-04-01 00:00:00"
    if len(s) >= 7 and s[4] == "-" and s[6].isdigit():
        return s[:7]
    return s

def _to_float(v: Any) -> float:
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    # números argentinos: "1.176.516" o "1.176.516,50"
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0

def _norm(s: Any) -> str:
    return str(s).strip() if s is not None else ""


def norm_rama(rama: Any) -> str:
    """Normaliza el nombre de rama para comparaciones."""
    return _norm(rama).upper().replace("  ", " ").strip()


def _nr_labels(rama: str) -> dict:
    """Nombres oficiales de los NR según rama (criterio César)."""
    r = _norm(rama).upper()
    if r in ("TURISMO", "CEREALES"):
        # En el maestro de Turismo/Cereales, suele venir 60k en no_rem y 40k en suma_fija.
        return {
            "no_rem": "Recomp. NR. Acu. 26",
            "suma_fija": "Incr. NR. Acu. Ene 26",
        }
    return {
        "no_rem": "Incr. NR. Acu. Dic 25",
        "suma_fija": "Recomp. NR. Acu. 25",
    }

# ---------------------------
# Maestro loader / parser
# ---------------------------

@lru_cache(maxsize=1)
def _load_wb() -> openpyxl.Workbook:
    return openpyxl.load_workbook(MAESTRO_PATH, data_only=True)

@lru_cache(maxsize=1)
def _build_index() -> Dict[str, Any]:
    wb = _load_wb()

    # salida
    payload: Dict[Tuple[str, str, str, str], Dict[str, float]] = {}
    ramas_set = set()
    meses_set = set()
    agrup_by_rama: Dict[str, set] = {}
    cat_by_rama_agrup: Dict[Tuple[str, str], set] = {}
    meses_by_rama: Dict[str, set] = {}

    def add_row(rama: str, agrup: str, cat: str, mes: str, bas: float, nr: float, sf: float):
        rama_u = _norm(rama).upper()
        agrup_u = _norm(agrup) if _norm(agrup) else "—"
        cat_u = _norm(cat) if _norm(cat) else "—"

        # Fix maestro FUNEBRES: a veces las categorías quedaron en "Agrupamiento" y "Categoria" viene vacío.
        if rama_u in ("FUNEBRES", "FÚNEBRES") and (cat_u == "—" or cat_u == "") and agrup_u not in ("—", ""):
            cat_u = agrup_u
            agrup_u = "—"
        mes_k = _mes_to_key(mes)

        if not rama_u or not mes_k:
            return

        payload[(rama_u, agrup_u, cat_u, mes_k)] = {"basico": bas, "no_rem": nr, "suma_fija": sf}
        ramas_set.add(rama_u)
        meses_set.add(mes_k)
        agrup_by_rama.setdefault(rama_u, set()).add(agrup_u)
        cat_by_rama_agrup.setdefault((rama_u, agrup_u), set()).add(cat_u)
        meses_by_rama.setdefault(rama_u, set()).add(mes_k)

    # --- Tabulares (GENERAL, TURISMO, FUNEBRES, CEREALES, CALL CENTER)
    for sh_name in wb.sheetnames:
        if not sh_name.startswith("Categorias_"):
            continue
        if sh_name == "Categorias_Agua_Potable":
            continue  # parse especial abajo

        ws = wb[sh_name]
        # headers en fila 1
        headers = [_norm(ws.cell(1, c).value).lower() for c in range(1, 10)]
        # buscamos indices
        def idx(name: str) -> Optional[int]:
            for i,h in enumerate(headers, start=1):
                if h == name:
                    return i
            return None

        i_rama = idx("rama") or 1
        i_agr = idx("agrupamiento") or 2
        i_cat = idx("categoria") or 3
        i_mes = idx("mes") or 4
        i_bas = idx("basico") or 5
        i_nr  = idx("no_rem") or 6
        i_sf  = idx("suma_fija") or 7

        for r in range(2, ws.max_row + 1):
            rama = ws.cell(r, i_rama).value
            if rama is None:
                continue
            mes = ws.cell(r, i_mes).value
            rama_u = _norm(rama).upper()
            agrup = ws.cell(r, i_agr).value
            cat = ws.cell(r, i_cat).value
            bas = _to_float(ws.cell(r, i_bas).value)
            nr  = _to_float(ws.cell(r, i_nr).value)
            sf  = _to_float(ws.cell(r, i_sf).value)
            add_row(rama_u, agrup, cat, mes, bas, nr, sf)

    # --- AGUA POTABLE (sheet no tabular, por bloques)
    if "Categorias_Agua_Potable" in wb.sheetnames:
        ws = wb["Categorias_Agua_Potable"]
        rama_u = "AGUA POTABLE"
        current_agr = "—"
        current_cat = ""
        in_table = False

        for r in range(1, ws.max_row + 1):
            a = ws.cell(r, 1).value
            b = ws.cell(r, 2).value
            c = ws.cell(r, 3).value
            d = ws.cell(r, 4).value

            a_s = _norm(a)

            # AGRUPAMIENTO:
            if isinstance(a, str) and a_s.upper().startswith("AGRUPAMIENTO"):
                # el valor puede venir en col 2
                current_agr = _norm(b) if _norm(b) else "—"
                in_table = False
                continue

            # Categoría:
            if isinstance(a, str) and a_s.upper().startswith("CATEGOR"):
                current_cat = _norm(b)
                in_table = False
                continue

            # header MES - AÑO
            if isinstance(a, str) and a_s.upper().startswith("MES"):
                in_table = True
                continue

            if not in_table:
                continue

            # filas de mes
            mes_k = _mes_to_key(a)
            if not mes_k or mes_k.lower().startswith("mes"):
                continue

            bas = _to_float(b)
            # En Agua Potable, los NR vienen como 2 columnas (incrementos NR) => los consolidamos en "suma_fija"
            sf = _to_float(c) + _to_float(d)
            nr = 0.0

            add_row(rama_u, current_agr or "—", current_cat or "—", mes_k, bas, nr, sf)

    # ---------------------------
    # Adicionales Fúnebres
    # ---------------------------
    # La hoja "Adicionales" del maestro puede venir en distintos formatos según versión.
    # Formato usual actual (enero 2026): Rama | Concepto | Mes | Valor | Detalle
    # Otros formatos posibles: Rama | Concepto | Mes | Tipo | Monto | % | Observación
    funebres_adic: Dict[str, List[Dict[str, Any]]] = {}  # mes -> list
    if "Adicionales" in wb.sheetnames:
        ws = wb["Adicionales"]

        # Mapear columnas por encabezados (fila 1)
        header = {}
        for c in range(1, ws.max_column + 1):
            h = _norm(ws.cell(1, c).value)
            if h:
                header[h.lower()] = c

        col_rama = header.get("rama", 1)
        col_concepto = header.get("concepto", 2)
        col_mes = header.get("mes", 3)
        col_tipo = header.get("tipo")  # opcional
        col_monto = header.get("monto") or header.get("valor") or header.get("importe")
        col_pct = header.get("%") or header.get("porcentaje") or header.get("pct")
        col_obs = header.get("observación") or header.get("observacion") or header.get("detalle") or header.get("obs")

        for r in range(2, ws.max_row + 1):
            rama = _norm(ws.cell(r, col_rama).value)
            if rama.lower() not in ["funebres", "fúnebres"]:
                continue

            concepto_raw = _norm(ws.cell(r, col_concepto).value)
            mes_k = _mes_to_key(ws.cell(r, col_mes).value)
            if not mes_k or not concepto_raw:
                continue

            tipo_raw = _norm(ws.cell(r, col_tipo).value).lower() if col_tipo else ""
            monto_val = _to_float(ws.cell(r, col_monto).value) if col_monto else 0.0
            pct_val = _to_float(ws.cell(r, col_pct).value) if col_pct else 0.0
            obs_raw = _norm(ws.cell(r, col_obs).value) if col_obs else ""

            # Determinar tipo
            tipo = "pct" if ("por" in tipo_raw or "%" in tipo_raw) else "monto"

            # Etiquetas amigables (como en el HTML offline)
            cl = concepto_raw.lower()
            label = concepto_raw
            if "indument" in cl:
                label = "Indumentaria"
            elif "general" in cl:
                # Ojo: este concepto suele venir como "... incluidos choferes", por eso
                # se evalúa ANTES que el de chofer/furgonero.
                label = "Resto del personal"
            elif "cadaver" in cl or "cadáver" in cl or "no incluido" in cl or "inciso" in cl:
                label = "Manipulación de cadáveres"
            elif "furgon" in cl or "chofer/furgon" in cl:
                label = "Chofer/Furgonero"

            funebres_adic.setdefault(mes_k, []).append({
                "id": concepto_raw,   # id estable (se usa en fun_adic[] del /calcular)
                "label": label,
                "tipo": tipo,
                "monto": monto_val if tipo == "monto" else 0.0,
                "pct": pct_val if tipo == "pct" else 0.0,
                "obs": obs_raw,
            })


    # ---------------------------
    # Build meta
    # ---------------------------
    ramas = sorted(ramas_set)
    meses = sorted(meses_set)

    agrupamientos: Dict[str, List[str]] = {}
    categorias: Dict[str, Dict[str, List[str]]] = {}

    for rama in ramas:
        agrupamientos[rama] = sorted(list(agrup_by_rama.get(rama, set())))
        categorias[rama] = {}
        for agr in agrupamientos[rama]:
            categorias[rama][agr] = sorted(list(cat_by_rama_agrup.get((rama, agr), set())))

    return {
        "payload": payload,
        "meta": {
            "ramas": ramas,
            "meses": meses,
            "agrupamientos": agrupamientos,
            "categorias": categorias,
        },
        "meses_by_rama": {k: sorted(list(v)) for k, v in meses_by_rama.items()},
        "funebres_adic": funebres_adic,
    }


# ---------------------------
# Public API (used by main.py)
# ---------------------------

def get_meta() -> Dict[str, Any]:
    return _build_index()["meta"]

def get_payload(
    rama: str,
    mes: str,
    agrup: str = "—",
    categoria: str = "—",
    conex_cat: str = "",
    conexiones: int = 0,
    fun_adic: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Devuelve los valores base del maestro para la combinación dada.

    Se usa en:
      - /payload (solo rama + mes)
      - /calcular (rama + mes + agrup + categoria) como base.
    """
    idx = _build_index()
    key = (_norm(rama).upper(), _norm(agrup) or "—", _norm(categoria) or "—", _mes_to_key(mes))
    rec = idx["payload"].get(key)

    if not rec:
        # fallback: algunos front mandan "—" en agrup/cat o vienen vacíos
        key2 = (_norm(rama).upper(), "—", "—", _mes_to_key(mes))
        rec = idx["payload"].get(key2)

    if not rec:
        return {
            "ok": False,
            "error": "No se encontró esa combinación en el maestro",
            "rama": _norm(rama).upper(),
            "agrup": _norm(agrup) or "—",
            "categoria": _norm(categoria) or "—",
            "mes": _mes_to_key(mes),
        }

    labels = _nr_labels(key[0])

    out = {"ok": True, "rama": key[0], "agrup": key[1], "categoria": key[2], "mes": key[3], **rec, "labels": labels}

    # Agua Potable: ajustar valores base según selector de conexiones (A/B/C/D)
    if norm_rama(key[0]) in ("AGUA POTABLE", "AGUA", "AGUAPOTABLE") and (conex_cat or conexiones):
        regla = match_regla_conexiones(conex_cat or conexiones)
        try:
            f = float(regla.get("factor", 1.0))
        except Exception:
            f = 1.0
        if f and f != 1.0:
            out["basico"] = _round2(out.get("basico", 0.0) * f)
            out["no_rem"] = _round2(out.get("no_rem", 0.0) * f)
            out["suma_fija"] = _round2(out.get("suma_fija", 0.0) * f)
            out["conex_cat"] = _norm(conex_cat).upper() if conex_cat else ""
            out["conexiones"] = int(conexiones or 0)

    return out

def calcular_payload(
    rama: str,
    agrup: str,
    categoria: str,
    mes: str,
    jornada: float = 48,
    anios_antig: float = 0,
    osecac: bool = True,
    afiliado: bool = False,
    sind_pct: float = 0,
    titulo_pct: float = 0,
    zona_pct: float = 0,
    fer_no_trab: int = 0,
    fer_trab: int = 0,
    aus_inj: int = 0,
    # Agua potable: selector A/B/C/D (impacta en básicos y NR). Se mantiene conexiones por compatibilidad.
    conex_cat: str = "",
    conexiones: int = 0,
    # Fúnebres: ids de adicionales seleccionados (coma-separados)
    fun_adic: str = "",
) -> Dict[str, Any]:
    """Cálculo del endpoint /calcular (servidor).

    El front NO calcula: solo renderiza.
    Devuelve items + totales numéricos para que el HTML muestre cada fila.

    Versión núcleo (GENERAL): Básico, Antigüedad, Presentismo, NR base y descuentos principales.
    """
    base = get_payload(rama=rama, mes=mes, agrup=agrup, categoria=categoria)
    if not base.get("ok"):
        return base

    # -------- Bases prorrateadas (48hs) --------
    j = float(jornada or 48)
    factor = (j / 48.0) if 48.0 else 1.0

    bas_base = float(base.get("basico", 0.0) or 0.0)
    nr_base = float(base.get("no_rem", 0.0) or 0.0)
    sf_base = float(base.get("suma_fija", 0.0) or 0.0)

    # Agua Potable: Conexiones (A/B/C/D) NO se muestra como adicional;
    # modifica directamente el valor del Básico y de los No Rem.
    is_agua = norm_rama(rama) in ("AGUA POTABLE", "AGUA", "AGUAPOTABLE")
    if is_agua:
        nivel = _norm(conex_cat).upper() if conex_cat else ""
        info = match_regla_conexiones(nivel if nivel else conexiones)
        fac = float(info.get("factor", 1.0) or 1.0)
        if fac and fac != 1.0:
            bas_base *= fac
            nr_base *= fac
            sf_base *= fac

    bas = bas_base * factor
    nr = nr_base * factor
    sf = sf_base * factor

    # -------- Cálculos núcleo --------
    # Remunerativos
    pct_ant = float(anios_antig or 0.0) * 0.01

    # Zona desfavorable (porcentaje sobre Básico prorrateado)
    try:
        zona_pct_f = float(zona_pct or 0.0)
    except Exception:
        zona_pct_f = 0.0
    zona_pct_f = max(0.0, zona_pct_f)
    zona = round2(bas * (zona_pct_f / 100.0)) if zona_pct_f else 0.0

    # Antigüedad: base incluye Zona (criterio del sistema para cálculos generales)
    base_ant = round2(bas + zona)
    antig = round2(base_ant * pct_ant)

    # Regla Presentismo: se pierde con 2 (dos) o más ausencias injustificadas.
    aus_dias = max(0, int(aus_inj or 0))
    presentismo_habil = (aus_dias < 2)
    # Presentismo: doceava parte de (Básico + Zona + Antigüedad)
    base_pres = round2(bas + zona + antig)
    presentismo = round2(base_pres / 12.0) if presentismo_habil else 0.0

    rem_total = round2(bas + zona + presentismo + antig)

    # No remunerativos (NR) + derivados (Antigüedad NR / Presentismo NR)
    nr_base_total = round2(nr + sf)
    antig_nr = round2(nr_base_total * pct_ant) if nr_base_total else 0.0
    # Presentismo sobre NR: misma lógica que REM (12ava parte), incluyendo Antigüedad NR.
    # Se pierde también si corresponde pérdida de presentismo por ausencias.
    presentismo_nr = (
        round2((nr_base_total + antig_nr) / 12.0)
        if (nr_base_total and presentismo_habil)
        else 0.0
    )

    nr_total = round2(nr_base_total + antig_nr + presentismo_nr)

    # -------- FUNEBRES: Adicionales (según maestro) --------
    fun_rows: List[Dict[str, Any]] = []
    if norm_rama(base["rama"]) in ("FUNEBRES", "FÚNEBRES"):
        sel_raw = (fun_adic or "").strip()
        if sel_raw:
            # IMPORTANTE: NO cortar por coma, porque algunos IDs contienen comas
            # (p.ej. "incluidos choferes"). Usamos solo ";" como separador.
            sel_ids = [s.strip() for s in sel_raw.split(";") if s.strip()]
            if sel_ids:
                defs = get_adicionales_funebres(mes)
                by_id = {str(d.get("id")): d for d in defs}
                for sid in sel_ids:
                    d = by_id.get(str(sid))
                    if not d:
                        continue
                    label = str(d.get("label") or sid)
                    tipo = str(d.get("tipo") or "").strip().lower()
                    monto = float(d.get("monto") or 0.0)
                    pct = float(d.get("pct") or 0.0)

                    val = 0.0
                    base_num = 0.0
                    if tipo in ("monto", "importe", "fijo") and monto:
                        # prorrateo por jornada
                        val = round2(monto * factor)
                    elif pct:
                        base_num = float(bas)
                        val = round2(bas * (pct / 100.0))
                    elif monto:
                        val = round2(monto * factor)

                    if val:
                        fun_rows.append({"label": label, "val": float(val), "base": float(base_num)})
                        rem_total = round2(rem_total + val)

    # -------- TURISMO: Adicional por Título --------
    # Se aplica sobre el básico (REM) y sobre el NR de $40.000 (en nuestro maestro = suma_fija).
    try:
        titulo_pct_f = float(titulo_pct or 0.0)
    except Exception:
        titulo_pct_f = 0.0
    titulo_pct_f = max(0.0, titulo_pct_f)

    titulo_rem = 0.0
    titulo_nr = 0.0
    if base["rama"] == "TURISMO" and titulo_pct_f > 0:
        titulo_rem = round2(bas * (titulo_pct_f / 100.0)) if bas else 0.0
        # Turismo: $40.000 NR corresponde a suma_fija (sf)
        titulo_nr = round2(sf * (titulo_pct_f / 100.0)) if sf else 0.0
        rem_total = round2(rem_total + titulo_rem)
        nr_total = round2(nr_total + titulo_nr)

    # -------- Feriados --------
    fer_no = max(0, int(fer_no_trab or 0))
    fer_si = max(0, int(fer_trab or 0))
    base_fer_rem = round2(bas + zona + antig)
    base_fer_nr = round2(nr_base_total + antig_nr)
    # Para mensualizados:
    # - Feriado NO trabajado: se suma la diferencia entre día feriado (1/25) y día normal incluido en el mensual (1/30).
    # - Feriado trabajado: se suma 1 día feriado (1/25).
    vdia25_rem = round2(base_fer_rem / 25.0) if base_fer_rem else 0.0
    vdia30_rem = round2(base_fer_rem / 30.0) if base_fer_rem else 0.0
    vdia25_nr = round2(base_fer_nr / 25.0) if base_fer_nr else 0.0
    vdia30_nr = round2(base_fer_nr / 30.0) if base_fer_nr else 0.0

    fer_no_rem = round2(fer_no * (vdia25_rem - vdia30_rem)) if fer_no else 0.0
    fer_si_rem = round2(fer_si * vdia25_rem) if fer_si else 0.0

    fer_no_nr = round2(fer_no * (vdia25_nr - vdia30_nr)) if fer_no else 0.0
    fer_si_nr = round2(fer_si * vdia25_nr) if fer_si else 0.0

    rem_total = round2(rem_total + fer_no_rem + fer_si_rem)
    nr_total = round2(nr_total + fer_no_nr + fer_si_nr)

    # -------- Ausencias injustificadas (descuento) --------
    base_dia_aus = round2((bas + zona + antig) / 30.0) if (bas or zona or antig) else 0.0
    aus_rem = round2(aus_dias * base_dia_aus) if aus_dias else 0.0

    # Base imponible para aportes: REM - ausencias
    rem_aportes = max(0.0, round2(rem_total - aus_rem))

    # Descuentos
    jub = round2(rem_aportes * 0.11)
    pami = round2(rem_aportes * 0.03)
    # Si tiene OSECAC, Obra Social 3% también se calcula sobre NR (criterio del sistema)
    os_base = round2((rem_aportes + nr_total) if bool(osecac) else rem_aportes)
    os_aporte = round2(os_base * 0.03) if bool(osecac) else 0.0
    osecac_100 = 100.0 if bool(osecac) else 0.0

    sind = 0.0
    if bool(afiliado) and float(sind_pct or 0) > 0:
        sind = round2((rem_aportes + nr_total) * (float(sind_pct) / 100.0))

    ded_total = round2(jub + pami + os_aporte + osecac_100 + sind + aus_rem)
    neto = round2((rem_total + nr_total) - ded_total)

    def item(concepto: str, r: float = 0.0, n: float = 0.0, d: float = 0.0, base_num: float = 0.0) -> Dict[str, Any]:
        out = {"concepto": concepto, "r": float(r), "n": float(n), "d": float(d)}
        if base_num:
            out["base"] = float(base_num)
        return out

    items: List[Dict[str, Any]] = [item("Básico", r=bas, base_num=bas)]

    if zona:
        items.append(item("Zona desfavorable", r=zona, base_num=bas))

    if antig:
        items.append(item("Antigüedad", r=antig, base_num=base_ant))

    # Presentismo: si se pierde por 2+ ausencias injustificadas, NO se muestra la fila (pedido César).
    if presentismo_habil and presentismo:
        items.append(item(
            "Presentismo",
            r=presentismo,
            base_num=base_pres,
        ))

    # Fúnebres: adicionales seleccionados (según maestro)
    if fun_rows:
        for fr in fun_rows:
            items.append(item(
                str(fr.get("label") or "Adicional"),
                r=float(fr.get("val") or 0.0),
                base_num=float(fr.get("base") or 0.0),
            ))



    # -------- Etapa 12: Mostrar adicionales (Turismo Título / Agua Conexiones) --------
    if titulo_rem:
        items.append(item(
            'Adicional por Título',
            r=titulo_rem,
            base_num=bas,
        ))
    if titulo_nr:
        items.append(item(
            'Adicional por Título (NR)',
            n=titulo_nr,
            base_num=sf,
        ))

    # Conexiones (Agua Potable): no se agrega fila, porque el selector modifica el básico y los NR.
    # Feriados (REM)
    if fer_no_rem:
        items.append(item(
            f"Feriado no trabajado ({fer_no} día{'s' if fer_no != 1 else ''})",
            r=fer_no_rem,
            base_num=base_fer_rem,
        ))
    if fer_si_rem:
        items.append(item(
            f"Feriado trabajado ({fer_si} día{'s' if fer_si != 1 else ''})",
            r=fer_si_rem,
            base_num=base_fer_rem,
        ))

    labels = _nr_labels(base["rama"])

    if nr:
        items.append(item(labels.get("no_rem", "No Remunerativo"), n=nr))
    if sf:
        items.append(item(labels.get("suma_fija", "Suma Fija (NR)"), n=sf))

    # Derivados sobre NR (desglosado como filas NR)
    if antig_nr:
        items.append(item("Antigüedad (NR)", n=antig_nr, base_num=nr_base_total))
    # Presentismo sobre NR: si se pierde por 2+ ausencias injustificadas, NO se muestra la fila.
    if presentismo_habil and presentismo_nr:
        items.append(item(
            "Presentismo (NR)",
            n=presentismo_nr,
            base_num=(nr_base_total + antig_nr),
        ))

    # Feriados (NR)
    if fer_no_nr:
        items.append(item(
            f"Feriado no trabajado (NR) ({fer_no} día{'s' if fer_no != 1 else ''})",
            n=fer_no_nr,
            base_num=base_fer_nr,
        ))
    if fer_si_nr:
        items.append(item(
            f"Feriado trabajado (NR) ({fer_si} día{'s' if fer_si != 1 else ''})",
            n=fer_si_nr,
            base_num=base_fer_nr,
        ))

    # Ausencias injustificadas (descuento) – reduce bases de aportes vía rem_aportes
    if aus_rem:
        items.append(item(
            f"Ausencias injustificadas ({aus_dias} día{'s' if aus_dias != 1 else ''})",
            d=aus_rem,
            base_num=base_dia_aus,
        ))

    items.append(item("Jubilación 11%", d=jub, base_num=rem_aportes))
    items.append(item("Ley 19.032 (PAMI) 3%", d=pami, base_num=rem_aportes))

    if bool(osecac):
        items.append(item("Obra Social 3%", d=os_aporte, base_num=os_base))
        items.append(item("OSECAC $100", d=osecac_100))
    else:
        items.append(item("Obra Social 3%", d=0.0, base_num=os_base))

    if sind:
        items.append(item(f"Sindicato {float(sind_pct):g}%", d=sind, base_num=(rem_aportes + nr_total)))

    return {
        "ok": True,
        "rama": base["rama"],
        "agrup": base["agrup"],
        "categoria": base["categoria"],
        "mes": base["mes"],
        "jornada": j,
        "anios_antig": float(anios_antig or 0),
        "osecac": bool(osecac),
        "afiliado": bool(afiliado),
        "sind_pct": float(sind_pct or 0),
        "titulo_pct": float(titulo_pct or 0),
        "zona_pct": float(zona_pct_f),

        "labels": labels,

        "basico_base": float(bas_base),
        "no_rem_base": float(nr_base),
        "suma_fija_base": float(sf_base),

        "basico": float(bas),
        "zona": float(zona),
        "no_rem": float(nr),
        "suma_fija": float(sf),

        "items": items,
        "totales": {
            "rem": float(rem_total),
            "nr": float(nr_total),
            "ded": float(ded_total),
            "neto": float(neto),
        },
    }


def get_adicionales_funebres(mes: str) -> List[Dict[str, Any]]:
    """Adicionales de Fúnebres.

    - Si existe definición exacta para el mes, se usa esa.
    - Si no existe, se toma la última definición anterior (prórroga automática).
      Esto permite, por ejemplo, que si el maestro quedó hasta 2026-01, en
      2026-02/03/04 se sigan ofreciendo los mismos adicionales.
    """
    idx = _build_index()
    mes_k = _mes_to_key(mes)

    d = idx.get("funebres_adic", {})
    if mes_k in d:
        return list(d.get(mes_k, []))

    # fallback: última definición <= mes_k
    keys = [k for k in d.keys() if isinstance(k, str) and k <= mes_k]
    if not keys:
        return []
    best = max(keys)
    return list(d.get(best, []))

def match_regla_conexiones(conexiones_o_nivel) -> Dict[str, Any]:
    """
    Agua Potable: reglas por umbrales (según tu UI):
    A: hasta 500
    B: 501-1000
    C: 1001-1600
    D: más de 1600
    El % es 7% encadenado (A=0%, B=7%, C=14,49%, D=22,5043%).
    """
    # Soporta dos entradas:
    # 1) cantidad (int) -> determina A/B/C/D por umbral
    # 2) nivel directo ("A"/"B"/"C"/"D") -> usa ese nivel
    level = 0
    cat = None
    label = None
    if isinstance(conexiones_o_nivel, str) and conexiones_o_nivel.strip():
        c = _norm(conexiones_o_nivel).upper()
        if c in ["A", "B", "C", "D"]:
            cat = c
            level = {"A": 0, "B": 1, "C": 2, "D": 3}[c]
            label = {
                "A": "A (hasta 500)",
                "B": "B (+7% s/A)",
                "C": "C (+7% s/B)",
                "D": "D (+7% s/C)",
            }[c]
        else:
            # Si viene un texto no esperado, intentamos tratarlo como número
            try:
                conexiones_o_nivel = int(c)
            except Exception:
                conexiones_o_nivel = 0

    if cat is None:
        try:
            n = int(conexiones_o_nivel)
        except Exception:
            n = 0
        if n <= 0:
            return {"cat": None, "pct": 0.0, "factor": 1.0, "label": None}

        if n <= 500:
            level = 0
            cat = "A"
            label = "A (hasta 500)"
        elif n <= 1000:
            level = 1
            cat = "B"
            label = "B (501 a 1000)"
        elif n <= 1600:
            level = 2
            cat = "C"
            label = "C (1001 a 1600)"
        else:
            level = 3
            cat = "D"
            label = "D (más de 1600)"

    factor = 1.07 ** level
    pct = factor - 1.0  # level 0 => 0
    return {"cat": cat, "pct": pct, "factor": factor, "label": label}

def get_titulo_pct_por_nivel(nivel: str) -> float:
    n = _norm(nivel).lower()
    if n in ["terciario", "terciario_turismo", "terciario (2.5%)", "2.5", "2,5"]:
        return 2.5
    if n in ["universitario", "licenciatura", "universitario (5%)", "5"]:
        return 5.0
    return 0.0

def get_regla_cajero(tipo: str) -> Dict[str, Any]:
    """
    Regla (CCT 130/75 - Acuerdo 26/09/1983):
      - Cajeros A y C: 12,25% sobre básico inicial Cajeros A
      - Cajeros B: 48% sobre básico inicial Cajeros B
    """
    t = _norm(tipo).upper()
    if t in ["A", "CAJERO A", "CAJEROS A", "CAJERO C", "CAJEROS C", "C"]:
        return {"tipo": t, "pct": 12.25}
    if t in ["B", "CAJERO B", "CAJEROS B"]:
        return {"tipo": t, "pct": 48.0}
    return {"tipo": t, "pct": 0.0}

def get_regla_km(categoria: str, km: float) -> Dict[str, Any]:
    """Normaliza el input de KM para el endpoint /regla-km.

    El motor (y/o el front) puede decidir si aplica la regla <=100 o >100.
    Acá devolvemos ambos tramos ya separados.
    """
    try:
        k = float(km or 0)
    except Exception:
        k = 0.0

    km_le_100 = min(k, 100.0)
    km_gt_100 = max(k - 100.0, 0.0)

    return {
        "categoria": _norm(categoria),
        "km": k,
        "km_le_100": km_le_100,
        "km_gt_100": km_gt_100,
    }
