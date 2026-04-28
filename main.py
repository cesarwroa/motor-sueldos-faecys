import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import time
import uuid

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from escalas import (
    get_meta,
    get_payload,
    calcular_payload,
    get_adicionales_funebres,
    match_regla_conexiones,
    get_titulo_pct_por_nivel,
    get_regla_cajero,
    get_regla_km,
    calcular_final_payload,
)

app = FastAPI(title="motor-sueldos-faecys")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
ADMIN_LOGIN_EMAIL = os.getenv("ADMIN_LOGIN_EMAIL", "cesarwroa@gmail.com").strip().lower()
ADMIN_LOGIN_PASSWORD = os.getenv("ADMIN_LOGIN_PASSWORD", "Dni27941408")
ADMIN_ACCESS_SECRET = os.getenv("ADMIN_ACCESS_SECRET", "co-admin-access-2026-change-me")
ADMIN_TOKEN_TTL_SECONDS = int(os.getenv("ADMIN_TOKEN_TTL_SECONDS", "43200"))
ADMIN_FEATURES_FILE = BASE_DIR / "data" / "admin_features.json"
ADMIN_COMPANIES_FILE = BASE_DIR / "data" / "admin_companies.json"
FEATURE_ACCESS_ALLOWED = {"off", "admin_only", "public"}
FEATURE_PUBLIC_MAP = {
    "liquidacion_final": "liquidacion_final_publica",
}
DEFAULT_FEATURE_ACCESS = {
    "liquidacion_final": "admin_only",
    "registro_empresas": "admin_only",
    "portal_empresa": "admin_only",
    "firma_digital": "admin_only",
    "portal_empleado": "admin_only",
}
DEFAULT_PUBLIC_FEATURES = {
    "liquidacion_final_publica": False,
}


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminFeaturesUpdate(BaseModel):
    liquidacion_final: Optional[str] = None
    registro_empresas: Optional[str] = None
    portal_empresa: Optional[str] = None
    firma_digital: Optional[str] = None
    portal_empleado: Optional[str] = None
    liquidacion_final_publica: Optional[bool] = None


class AdminCompanyCreate(BaseModel):
    razon_social: str
    cuit: str = ""
    rama: str = ""
    email: str = ""
    telefono: str = ""
    estado: str = "prueba"
    observaciones: str = ""


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def _sign_admin_token(payload: Dict[str, Any]) -> str:
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_raw)
    signature = hmac.new(
        ADMIN_ACCESS_SECRET.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_b64}.{_b64url_encode(signature)}"


def _issue_admin_token(email: str) -> str:
    now = int(time.time())
    payload = {
        "email": email,
        "role": "admin",
        "iat": now,
        "exp": now + ADMIN_TOKEN_TTL_SECONDS,
    }
    return _sign_admin_token(payload)


def _read_admin_token(token: str) -> Dict[str, Any]:
    try:
        payload_b64, signature_b64 = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Token admin inválido.") from exc

    expected_signature = hmac.new(
        ADMIN_ACCESS_SECRET.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    actual_signature = _b64url_decode(signature_b64)

    if not hmac.compare_digest(expected_signature, actual_signature):
        raise HTTPException(status_code=401, detail="Firma de sesión inválida.")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="No se pudo leer la sesión admin.") from exc

    exp = int(payload.get("exp") or 0)
    if exp <= int(time.time()):
        raise HTTPException(status_code=401, detail="La sesión admin venció.")

    if str(payload.get("role") or "").lower() != "admin":
        raise HTTPException(status_code=401, detail="La sesión no tiene permisos de administrador.")

    return payload


def _extract_admin_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Falta el token admin.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Formato de autorización inválido.")
    return token.strip()


def _default_feature_store() -> Dict[str, Any]:
    feature_access = dict(DEFAULT_FEATURE_ACCESS)
    return {
        "feature_access": feature_access,
        "public_features": _feature_access_to_public_features(feature_access),
        "updated_at": None,
        "updated_by": "",
    }


def _normalize_feature_access_value(value: Any, default: str) -> str:
    raw = str(value or "").strip().lower()
    if raw in FEATURE_ACCESS_ALLOWED:
        return raw
    return default


def _feature_access_to_public_features(feature_access: Dict[str, str]) -> Dict[str, bool]:
    public_features = dict(DEFAULT_PUBLIC_FEATURES)
    for feature_name, public_key in FEATURE_PUBLIC_MAP.items():
        public_features[public_key] = str(feature_access.get(feature_name) or "").strip().lower() == "public"
    return public_features


def _normalize_feature_store(raw: Any) -> Dict[str, Any]:
    store = _default_feature_store()
    if not isinstance(raw, dict):
        return store

    raw_access = raw.get("feature_access")
    if isinstance(raw_access, dict):
        for key, default_value in DEFAULT_FEATURE_ACCESS.items():
            if key in raw_access:
                store["feature_access"][key] = _normalize_feature_access_value(raw_access.get(key), default_value)

    raw_public = raw.get("public_features")
    if isinstance(raw_public, dict) and "liquidacion_final" not in (raw_access or {}):
        if "liquidacion_final_publica" in raw_public and bool(raw_public.get("liquidacion_final_publica")):
            store["feature_access"]["liquidacion_final"] = "public"

    store["public_features"] = _feature_access_to_public_features(store["feature_access"])

    updated_at = raw.get("updated_at")
    if isinstance(updated_at, str) and updated_at.strip():
        store["updated_at"] = updated_at.strip()

    updated_by = raw.get("updated_by")
    if isinstance(updated_by, str):
        store["updated_by"] = updated_by.strip()

    return store


def _read_feature_store() -> Dict[str, Any]:
    if not ADMIN_FEATURES_FILE.exists():
        return _default_feature_store()

    try:
        raw = json.loads(ADMIN_FEATURES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        raw = {}
    return _normalize_feature_store(raw)


def _write_feature_store(store: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _normalize_feature_store(store)
    ADMIN_FEATURES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = ADMIN_FEATURES_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(ADMIN_FEATURES_FILE)
    return normalized


def _feature_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _public_feature_payload(store: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": True,
        "public_features": dict(store.get("public_features") or {}),
        "updated_at": store.get("updated_at"),
    }


def _admin_feature_payload(store: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": True,
        "feature_access": dict(store.get("feature_access") or {}),
        "public_features": dict(store.get("public_features") or {}),
        "updated_at": store.get("updated_at"),
        "updated_by": store.get("updated_by") or "",
    }


def _require_admin_session(authorization: Optional[str]) -> Dict[str, Any]:
    return _read_admin_token(_extract_admin_token(authorization))


def _optional_admin_session(authorization: Optional[str]) -> Optional[Dict[str, Any]]:
    if not authorization:
        return None
    return _read_admin_token(_extract_admin_token(authorization))


def _is_public_feature_enabled(feature_name: str) -> bool:
    store = _read_feature_store()
    public_features = store.get("public_features") or {}
    return bool(public_features.get(feature_name))


def _get_feature_access(feature_name: str) -> str:
    store = _read_feature_store()
    feature_access = store.get("feature_access") or {}
    default_value = DEFAULT_FEATURE_ACCESS.get(feature_name, "off")
    return _normalize_feature_access_value(feature_access.get(feature_name), default_value)


def _require_admin_feature_access(authorization: Optional[str], feature_name: str) -> Dict[str, Any]:
    admin_payload = _require_admin_session(authorization)
    access = _get_feature_access(feature_name)
    if access not in {"admin_only", "public"}:
        raise HTTPException(status_code=403, detail="La función todavía no está habilitada en el panel.")
    return admin_payload


def _read_admin_companies() -> List[Dict[str, Any]]:
    if not ADMIN_COMPANIES_FILE.exists():
        return []

    try:
        raw = json.loads(ADMIN_COMPANIES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        raw = []

    if not isinstance(raw, list):
        return []

    companies: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        razon_social = str(item.get("razon_social") or "").strip()
        if not razon_social:
            continue
        companies.append(
            {
                "id": str(item.get("id") or "").strip() or uuid.uuid4().hex[:12],
                "razon_social": razon_social,
                "cuit": str(item.get("cuit") or "").strip(),
                "rama": str(item.get("rama") or "").strip(),
                "email": str(item.get("email") or "").strip(),
                "telefono": str(item.get("telefono") or "").strip(),
                "estado": str(item.get("estado") or "prueba").strip() or "prueba",
                "observaciones": str(item.get("observaciones") or "").strip(),
                "created_at": str(item.get("created_at") or "").strip(),
                "updated_at": str(item.get("updated_at") or item.get("created_at") or "").strip(),
                "created_by": str(item.get("created_by") or "").strip(),
            }
        )
    return companies


def _write_admin_companies(companies: List[Dict[str, Any]]) -> None:
    ADMIN_COMPANIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = ADMIN_COMPANIES_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(companies, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(ADMIN_COMPANIES_FILE)

# ========= HOME → HTML =========
@app.get("/", include_in_schema=False)
def home():
    p = BASE_DIR / "index.html"
    if p.exists():
        return FileResponse(p)

    p2 = BASE_DIR / "static" / "index.html"
    if p2.exists():
        return FileResponse(p2)

    return {"ok": True, "error": "index.html no encontrado"}

# ========= HEALTH =========
@app.get("/health")
def health():
    return {"ok": True, "servicio": "motor-sueldos-faecys"}


@app.post("/admin/login")
def admin_login(payload: AdminLoginRequest):
    email = payload.email.strip().lower()
    password = payload.password

    valid_email = hmac.compare_digest(email, ADMIN_LOGIN_EMAIL)
    valid_password = hmac.compare_digest(password, ADMIN_LOGIN_PASSWORD)

    if not (valid_email and valid_password):
        raise HTTPException(status_code=401, detail="Credenciales de administrador inválidas.")

    return {
        "ok": True,
        "token": _issue_admin_token(email),
        "email": ADMIN_LOGIN_EMAIL,
        "role": "admin",
        "expires_in": ADMIN_TOKEN_TTL_SECONDS,
    }


@app.get("/admin/session")
def admin_session(authorization: Optional[str] = Header(default=None)):
    payload = _require_admin_session(authorization)
    return {
        "ok": True,
        "authenticated": True,
        "role": payload["role"],
        "email": payload["email"],
        "expires_at": payload["exp"],
    }


@app.get("/features")
def public_features():
    store = _read_feature_store()
    return _public_feature_payload(store)


@app.get("/admin/features")
def admin_features(authorization: Optional[str] = Header(default=None)):
    _require_admin_session(authorization)
    store = _read_feature_store()
    return _admin_feature_payload(store)


@app.put("/admin/features")
def update_admin_features(payload: AdminFeaturesUpdate, authorization: Optional[str] = Header(default=None)):
    admin_payload = _require_admin_session(authorization)
    store = _read_feature_store()
    feature_access = dict(store.get("feature_access") or {})
    public_features = dict(store.get("public_features") or {})

    for feature_name in DEFAULT_FEATURE_ACCESS:
        next_value = getattr(payload, feature_name, None)
        if next_value is not None:
            feature_access[feature_name] = _normalize_feature_access_value(next_value, DEFAULT_FEATURE_ACCESS[feature_name])

    if payload.liquidacion_final_publica is not None and payload.liquidacion_final is None:
        feature_access["liquidacion_final"] = "public" if bool(payload.liquidacion_final_publica) else "admin_only"

    public_features = _feature_access_to_public_features(feature_access)
    store["feature_access"] = feature_access
    store["public_features"] = public_features
    store["updated_at"] = _feature_timestamp()
    store["updated_by"] = str(admin_payload.get("email") or ADMIN_LOGIN_EMAIL).strip().lower()

    try:
        saved = _write_feature_store(store)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="No se pudo guardar la configuraciÃ³n del panel.") from exc
    return _admin_feature_payload(saved)


@app.get("/admin/companies")
def admin_companies(authorization: Optional[str] = Header(default=None)):
    _require_admin_feature_access(authorization, "registro_empresas")
    items = sorted(_read_admin_companies(), key=lambda item: (item.get("razon_social") or "").lower())
    return {
        "ok": True,
        "items": items,
        "count": len(items),
    }


@app.post("/admin/companies")
def create_admin_company(payload: AdminCompanyCreate, authorization: Optional[str] = Header(default=None)):
    admin_payload = _require_admin_feature_access(authorization, "registro_empresas")
    razon_social = payload.razon_social.strip()
    if not razon_social:
        raise HTTPException(status_code=400, detail="La razón social es obligatoria.")

    companies = _read_admin_companies()
    now = _feature_timestamp()
    company = {
        "id": uuid.uuid4().hex[:12],
        "razon_social": razon_social,
        "cuit": payload.cuit.strip(),
        "rama": payload.rama.strip(),
        "email": payload.email.strip(),
        "telefono": payload.telefono.strip(),
        "estado": payload.estado.strip() or "prueba",
        "observaciones": payload.observaciones.strip(),
        "created_at": now,
        "updated_at": now,
        "created_by": str(admin_payload.get("email") or ADMIN_LOGIN_EMAIL).strip().lower(),
    }
    companies.append(company)

    try:
        _write_admin_companies(companies)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="No se pudo guardar la empresa de prueba.") from exc

    return {
        "ok": True,
        "item": company,
        "count": len(companies),
    }

# ========= META =========
@app.get("/meta")
def meta():
    return get_meta()

# ========= PAYLOAD (bases del maestro) =========
@app.get("/payload")
def payload(
    rama: str,
    mes: str,
    agrup: str = "—",
    categoria: str = "—",
    conex_cat: str = "",
    conexiones: int = 0,
):
    return get_payload(
        rama=rama,
        mes=mes,
        agrup=agrup,
        categoria=categoria,
        conex_cat=conex_cat,
        conexiones=conexiones,
    )

# ========= CALCULAR (recibo completo) =========
@app.get("/calcular")
def calcular(
    rama: str,
    agrup: str,
    categoria: str,
    mes: str,
    jornada: float = 48.0,
    anios_antig: float = 0,
    osecac: bool = True,
    afiliado: bool = False,
    sind_pct: float = 0,
    sind_fijo: float = 0,
    titulo_pct: float = 0,
    zona_pct: float = 0,
    fer_no_trab: int = 0,
    fer_trab: int = 0,
    vac_goz: int = 0,
    aus_inj: int = 0,
    jubilado: bool = False,
    susp_dias: int = 0,
    embargo: float = 0,
    # Horas
    hex50: float = 0,
    hex100: float = 0,
    hs_noct: float = 0,
    # KM (Chofer/Ayudante)
    km_tipo: str = "",
    km_menos100: float = 0,
    km_mas100: float = 0,
    # Etapa 5/6: A cuenta (REM) / Viáticos (NR sin aportes)
    a_cuenta_rem: float = 0,
    viaticos_nr: float = 0,

    # Etapa 7: Manejo de Caja / Vidriera / Adelanto
    manejo_caja: bool = False,
    cajero_tipo: str = "",
    faltante_caja: float = 0,
    armado_vidriera: bool = False,
    adelanto_sueldo: float = 0,
    sac_prop_mes: bool = False,
    # Agua potable: selector A/B/C/D. Se mantiene conexiones por compatibilidad.
    conex_cat: str = "",
    conexiones: int = 0,
    # Fúnebres: ids de adicionales seleccionados (coma-separados)
    fun_adic: Optional[List[str]] = Query(None),
):
    return calcular_payload(
        rama=rama,
        agrup=agrup,
        categoria=categoria,
        mes=mes,
        jornada=jornada,
        anios_antig=anios_antig,
        osecac=osecac,
        afiliado=afiliado,
        sind_pct=sind_pct,
        sind_fijo=sind_fijo,
        titulo_pct=titulo_pct,
        zona_pct=zona_pct,
        fer_no_trab=fer_no_trab,
        fer_trab=fer_trab,
        vac_goz=vac_goz,
        aus_inj=aus_inj,
        jubilado=jubilado,
        susp_dias=susp_dias,
        embargo=embargo,
        hex50=hex50,
        hex100=hex100,
        hs_noct=hs_noct,
        km_tipo=km_tipo,
        km_menos100=km_menos100,
        km_mas100=km_mas100,
        a_cuenta_rem=a_cuenta_rem,
        viaticos_nr=viaticos_nr,
        manejo_caja=manejo_caja,
        cajero_tipo=cajero_tipo,
        faltante_caja=faltante_caja,
        armado_vidriera=armado_vidriera,
        adelanto_sueldo=adelanto_sueldo,
        sac_prop_mes=sac_prop_mes,
        conex_cat=conex_cat,
        conexiones=conexiones,
        fun_adic=(";".join(fun_adic) if fun_adic else ""),
    )



# ========= CALCULAR FINAL (liquidación final) =========
@app.get("/calcular-final")
def calcular_final(
    rama: str,
    agrup: str,
    categoria: str,
    fecha_ingreso: str,
    fecha_egreso: str,
    jornada: float = 48.0,
    tipo: str = "RENUNCIA",
    # Mejor salario mensual normal y habitual (ideal: desglosado)
    mejor_rem: float = 0,
    mejor_nr: float = 0,
    mejor_total: float = 0,
    # Parámetros
    dias_mes: int = 0,
    vac_anuales: int = 14,
    vac_no_gozadas_dias: float = 0.0,
    preaviso_dias: int = 0,
    integracion: bool = True,
    sac_preaviso: bool = False,
    sac_integracion: bool = True,
    # Mismos flags/descuentos que mensual
    osecac: bool = True,
    afiliado: bool = False,
    sind_pct: float = 0,
    sind_fijo: float = 0,
    titulo_pct: float = 0,
    zona_pct: float = 0,
    fer_no_trab: int = 0,
    fer_trab: int = 0,
    vac_goz: int = 0,
    aus_inj: int = 0,
    susp_dias: int = 0,
    hex50: float = 0,
    hex100: float = 0,
    hs_noct: float = 0,
    km_tipo: str = "",
    km_menos100: int = 0,
    km_mas100: int = 0,
    a_cuenta_rem: float = 0,
    viaticos_nr: float = 0,
    manejo_caja: bool = False,
    cajero_tipo: str = "",
    faltante_caja: float = 0,
    armado_vidriera: bool = False,
    adelanto_sueldo: float = 0,
    fun_adic: Optional[List[str]] = Query(default=[]),
    jubilado: bool = False,
    embargo: float = 0,
    authorization: Optional[str] = Header(default=None),
):
    public_enabled = _is_public_feature_enabled("liquidacion_final_publica")
    admin_session = _optional_admin_session(authorization)
    if not public_enabled and not admin_session:
        raise HTTPException(status_code=403, detail="LiquidaciÃ³n Final disponible solo para administrador.")

    return calcular_final_payload(
        rama=rama,
        agrup=agrup,
        categoria=categoria,
        jornada=jornada,
        fecha_ingreso=fecha_ingreso,
        fecha_egreso=fecha_egreso,
        tipo=tipo,
        mejor_rem=mejor_rem,
        mejor_nr=mejor_nr,
        mejor_total=mejor_total,
        dias_mes=dias_mes,
        vac_anuales=vac_anuales,
        vac_no_gozadas_dias=vac_no_gozadas_dias,
        preaviso_dias=preaviso_dias,
        integracion=integracion,
        sac_sobre_preaviso=sac_preaviso,
        sac_sobre_integracion=sac_integracion,
        osecac=osecac,
        afiliado=afiliado,
        sind_pct=sind_pct,
        sind_fijo=sind_fijo,
        titulo_pct=titulo_pct,
        zona_pct=zona_pct,
        fer_no_trab=fer_no_trab,
        fer_trab=fer_trab,
        vac_goz=vac_goz,
        aus_inj=aus_inj,
        susp_dias=susp_dias,
        hex50=hex50,
        hex100=hex100,
        hs_noct=hs_noct,
        km_tipo=km_tipo,
        km_menos100=km_menos100,
        km_mas100=km_mas100,
        a_cuenta_rem=a_cuenta_rem,
        viaticos_nr=viaticos_nr,
        manejo_caja=manejo_caja,
        cajero_tipo=cajero_tipo,
        faltante_caja=faltante_caja,
        armado_vidriera=armado_vidriera,
        adelanto_sueldo=adelanto_sueldo,
        fun_adic=(";".join(fun_adic) if fun_adic else ""),
        jubilado=jubilado,
        embargo=embargo,
    )
# ========= FUNEBRES =========
@app.get("/adicionales-funebres")
def adicionales_funebres(mes: str):
    return get_adicionales_funebres(mes)

# ========= AGUA POTABLE =========
@app.get("/regla-conexiones")
def regla_conexiones(cantidad: int = 0, nivel: str = ""):
    # Si el front manda nivel (A/B/C/D), devolvemos la misma estructura.
    if nivel:
        return match_regla_conexiones(nivel)
    return match_regla_conexiones(cantidad)

# ========= TURISMO =========
@app.get("/titulo-pct")
def titulo_pct(nivel: str):
    return get_titulo_pct_por_nivel(nivel)

# ========= CAJEROS =========
@app.get("/regla-cajero")
def regla_cajero(tipo: str):
    return get_regla_cajero(tipo)

# ========= KM =========
@app.get("/regla-km")
def regla_km(categoria: str, km: float):
    return get_regla_km(categoria, km)
