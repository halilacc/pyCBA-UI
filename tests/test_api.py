"""HTTP API testleri — taşıma katmanı; hesap doğruluğu test_core.py'dedir."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.index import app

istemci = TestClient(app)

REFERANS = {
    "spans": [6, 6], "EI": [30000, 30000], "supports": ["pin", "roller", "pin"],
    "loads": [{"span": 1, "kind": "udl", "values": [20]},
              {"span": 2, "kind": "udl", "values": [20]}],
}


def test_meta_yuk_tipleri_ve_iki_dil():
    m = istemci.get("/api/meta").json()
    assert m["load_types"]["udl"] == {"params": ["w"], "axial": False}
    assert m["load_types"]["axial_udl"]["axial"] is True
    assert set(m["metinler"]) == {"tr", "en"}
    assert set(m["param_units"]) >= {p for v in m["load_types"].values() for p in v["params"]}


def test_referans_problem():
    # 2x6 m, 20 kN/m: M_B = -90 kNm, tepkiler 45/150/45 kN (kapalı formül)
    r = istemci.post("/api/analiz", json=REFERANS).json()
    assert r["hatalar"] == []
    s = r["sonuc"]
    assert [x["V"] for x in s["reactions"]] == pytest.approx([45, 150, 45], abs=1e-3)
    assert min(s["M"]) == pytest.approx(-90, abs=0.1)
    assert s["node_x"] == [0, 6, 12]
    assert r["sema_svg"].lstrip().startswith(("<?xml", "<svg"))


def test_dogrulama_hatasi_dile_gore():
    kotu = {**REFERANS, "EI": [30000]}
    tr = istemci.post("/api/analiz", json=kotu).json()
    en = istemci.post("/api/analiz", json={**kotu, "dil": "en"}).json()
    assert tr["hatalar"] and en["hatalar"] and tr["hatalar"] != en["hatalar"]
    assert tr["sonuc"] is None


def test_yuk_yoksa_yalniz_sema():
    r = istemci.post("/api/analiz", json={**REFERANS, "loads": []}).json()
    assert r["hatalar"] == [] and r["sonuc"] is None and r["sema_svg"]


def test_mekanizma_hata_verir_ama_sema_gelir():
    r = istemci.post("/api/analiz", json={
        **REFERANS, "supports": ["pin", "free", "roller"], "hinges": [2],
        "loads": [{"span": 1, "kind": "udl", "values": [10]}],
    }).json()
    assert r["hatalar"] and r["sonuc"] is None


def test_cokme_mm_asagi_pozitif_sehime_asagi_negatif_yansir():
    # Ara mesnet 10 mm ASAĞI çökerse o düğümde sehim -0.010 m olmalı (D: aşağı eksi)
    g = {**REFERANS, "loads": [], "settlements_mm": {2: 10}}
    s = istemci.post("/api/analiz", json=g).json()["sonuc"]
    assert min(s["D"]) == pytest.approx(-0.010, abs=1e-6)
    assert s["has_settlements"]


def test_eksenel_yuk_normal_kuvvet_dizisi_getirir():
    g = {**REFERANS, "loads": [{"span": 1, "kind": "axial_point", "values": [10, 3]}]}
    s = istemci.post("/api/analiz", json=g).json()["sonuc"]
    assert s["has_axial"] and np.max(np.abs(s["N"])) > 0
