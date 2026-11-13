"""
PyCBA HTTP API — FastAPI.

Yalnızca taşıma katmanı: hesap `core/`, şema çizimi `ui_cizim.py`, metinler
`ui_dil.py` / `core/mesajlar.py` içindedir; burada hiçbiri yeniden yazılmaz.
Çalıştırma: .venv\\Scripts\\python.exe -m uvicorn api.index:app --port 8000

Birimler ve işaretler ön yüze çekirdekle AYNI gider (kN, m, kNm²; sehim metre),
tek istisna mesnet çökmesi: ön yüz Streamlit'teki gibi "mm, aşağı pozitif"
sorar, m + core işaretine (aşağı negatif) çeviri `modeli_kur`da, tek yerde.
"""

import io
from typing import Dict, List, Optional

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from matplotlib.figure import Figure
from pydantic import BaseModel, Field

from core import (
    AXIAL_KINDS, BeamModel, Load, LOAD_TYPES, SUPPORT_TYPES, SolverError, solve,
)
from ui_cizim import NORMAL_KUVVET_YESILI, ciz_sema
from ui_dil import DILLER, METINLER, VARSAYILAN_DIL

# Yük parametresi -> birim (app.PARAM_UNITS ile aynı; app.py artık tek başına
# bir arayüz, ona bağımlı olmamak için burada).
PARAM_UNITS = {
    "w": "kN/m", "w1": "kN/m", "w2": "kN/m", "P": "kN", "M": "kNm",
    "a": "m", "c": "m", "N": "kN", "n": "kN/m",
}

app = FastAPI(title="PyCBA API", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=1000)
# Ön yüz aynı kökenden (Next rewrites) konuşur; CORS yalnız geliştirme içindir.
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:3000"],
    allow_methods=["*"], allow_headers=["*"],
)


class YukGirdi(BaseModel):
    span: int
    kind: str
    values: List[float]


class ModelGirdi(BaseModel):
    spans: List[float]
    EI: List[float]
    supports: List[str]
    loads: List[YukGirdi] = Field(default_factory=list)
    hinges: List[int] = Field(default_factory=list)
    # (açıklık no, sol uçtan a [m]) çiftleri
    span_hinges: List[List[float]] = Field(default_factory=list)
    springs: Dict[int, float] = Field(default_factory=dict)
    # mm, AŞAĞI POZİTİF (arayüz konvansiyonu)
    settlements_mm: Dict[int, float] = Field(default_factory=dict)
    dil: str = VARSAYILAN_DIL


def modeli_kur(g: ModelGirdi) -> BeamModel:
    return BeamModel(
        spans=g.spans, EI=g.EI, supports=g.supports,
        loads=[Load(y.span, y.kind, list(y.values)) for y in g.loads],
        hinges=g.hinges,
        span_hinges=[(int(s), float(a)) for s, a in g.span_hinges],
        springs=g.springs,
        # mm -> m ve işaret çevirisi (aşağı negatif); sıfır çökme hiç gönderilmez
        settlements={n: -v / 1000.0 for n, v in g.settlements_mm.items()
                     if abs(v) > 1e-12},
    )


def _sema_svg(model: BeamModel, reactions, dil: str) -> str:
    # `Figure` doğrudan (pyplot DEĞİL): global kayıt, çok iş parçacıklı sunucuda
    # yarışa açıktır (bkz. CLAUDE.md "Şema figürü").
    fig = Figure(figsize=(10, 3.4))
    ciz_sema(fig.subplots(), model, reactions, dil)
    buf = io.StringIO()
    fig.savefig(buf, format="svg", transparent=True)
    return buf.getvalue()


def _dizi(a) -> list:
    return np.round(np.asarray(a, dtype=float), 6).tolist()


@app.get("/api/meta")
def meta():
    """Ön yüzün ihtiyaç duyduğu sabitler: yük/mesnet tipleri, birimler, metinler."""
    return {
        "load_types": {k: {"params": v[2], "axial": k in AXIAL_KINDS}
                       for k, v in LOAD_TYPES.items()},
        "support_types": SUPPORT_TYPES,
        "param_units": PARAM_UNITS,
        "diller": DILLER,
        "varsayilan_dil": VARSAYILAN_DIL,
        "metinler": METINLER,
        "normal_kuvvet_yesili": NORMAL_KUVVET_YESILI,
    }


@app.post("/api/analiz")
def analiz(g: ModelGirdi):
    """Doğrula, çöz, şemayı çiz. Hatalar 200 + `hatalar` listesiyle döner."""
    model = modeli_kur(g)
    try:
        hatalar = model.validate(g.dil)
    except Exception as e:  # bilinmeyen yük tipi vb.: kullanıcıya gösterilebilir
        hatalar = [str(e)]
    if hatalar:
        return {"hatalar": hatalar, "sema_svg": None, "sonuc": None}

    # Yük ve çökme yoksa çözüm (tepki) yok: yalnız şema.
    if not g.loads and not model.settlements:
        return {"hatalar": [], "sema_svg": _sema_svg(model, None, g.dil), "sonuc": None}

    try:
        r = solve(model, g.dil)
    except SolverError as e:
        # Çözülemese de şema yüklerle birlikte gösterilir (app.py ile aynı akış).
        return {"hatalar": [str(e)], "sema_svg": _sema_svg(model, None, g.dil),
                "sonuc": None}

    return {
        "hatalar": [],
        "sema_svg": _sema_svg(model, r["reactions"], g.dil),
        "sonuc": {
            "x": _dizi(r["x"]), "M": _dizi(r["M"]), "V": _dizi(r["V"]),
            "D": _dizi(r["D"]),  # metre
            "xN": _dizi(r["xN"]), "N": _dizi(r["N"]),
            "ea_uyari": bool(r["ea_uyari"]),
            "reactions": [
                {k: rr[k] for k in ("node", "x", "V", "M", "H")}
                for rr in r["reactions"]
            ],
            "has_axial": any(ld.kind in AXIAL_KINDS for ld in model.loads),
            "has_fixed": "fixed" in model.supports,
            "static_degree": model.static_degree(),
            "node_x": _dizi(np.concatenate([[0.0], np.cumsum(model.spans)])),
            "supports": model.supports,
            "has_settlements": bool(model.settlements),
        },
    }
