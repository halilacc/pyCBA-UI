"""Çekirdek regresyon testleri — arayüzsüz, elle doğrulanabilir vakalar.

Buradaki her vaka ya kapalı formülle ya da klasik statik çözümle elde
edilmiştir; PyCBA'nın çıktısını "olduğu gibi" dondurmaz. Amaç, `core/`de bir
değişiklik yapıldığında bilinen doğru sonuçların bozulup bozulmadığını anında
görmek.

Çalıştırma:  .venv\\Scripts\\python.exe -m pytest -q
"""

import pytest

from core import BeamModel, Load, SolverError, solve

TOL = 1e-6  # bağıl tolerans (çözümler analitik; sayısal gürültü çok küçük)


def _tepki(sonuc, dugum):
    """1-tabanlı düğüm no'suna ait düşey tepkiyi döndür."""
    for r in sonuc["reactions"]:
        if r["node"] == dugum:
            return r["V"]
    raise AssertionError(f"Düğüm {dugum} için tepki yok")


# --------------------------------------------------------- sürekli kiriş (referans)
def test_referans_surekli_kiris():
    """CLAUDE.md referans problemi: 2×6 m, her açıklıkta 20 kN/m UDL.

    Simetrik iki eşit açıklık, tam UDL: M_B = -w·L²/8 = -90 kNm,
    tepkiler 3wL/8 = 45 · 10wL/8 = 150 · 45 kN.
    """
    model = BeamModel(
        spans=[6.0, 6.0], EI=[30_000.0] * 2,
        supports=["pin", "roller", "pin"],
        loads=[Load(1, "udl", [20.0]), Load(2, "udl", [20.0])],
    )
    assert model.validate() == []
    assert model.static_degree() == 1  # bir kez hiperstatik
    r = solve(model)
    assert r["Mmin"] == pytest.approx(-90.0, rel=1e-4)
    assert _tepki(r, 1) == pytest.approx(45.0, rel=1e-4)
    assert _tepki(r, 2) == pytest.approx(150.0, rel=1e-4)
    assert _tepki(r, 3) == pytest.approx(45.0, rel=1e-4)


def test_basit_kiris_udl():
    """Basit kiriş + tam UDL: M_max = wL²/8, tepkiler wL/2, f = 5wL⁴/(384EI)."""
    w, L, EI = 12.0, 8.0, 25_000.0
    model = BeamModel(spans=[L], EI=[EI], supports=["pin", "roller"],
                      loads=[Load(1, "udl", [w])])
    r = solve(model)
    assert r["Mmax"] == pytest.approx(w * L**2 / 8, rel=1e-4)
    assert _tepki(r, 1) == pytest.approx(w * L / 2, rel=1e-6)
    assert _tepki(r, 2) == pytest.approx(w * L / 2, rel=1e-6)
    # Sehim aşağı (negatif) — mutlak değeri kapalı formülle karşılaştırılır.
    assert abs(r["Dmin"]) == pytest.approx(5 * w * L**4 / (384 * EI), rel=1e-3)


def test_konsol_ucta_tekil_yuk():
    """Ankastre konsol, uçta P: mesnette M = -P·L, tepki = P."""
    P, L = 15.0, 4.0
    model = BeamModel(spans=[L], EI=[20_000.0], supports=["fixed", "free"],
                      loads=[Load(1, "point", [P, L])])
    r = solve(model)
    assert _tepki(r, 1) == pytest.approx(P, rel=1e-6)
    assert r["Mmin"] == pytest.approx(-P * L, rel=1e-4)


# ------------------------------------------------------------------ Gerber (mafsal)
def test_eletype_esleme():
    """Mafsal SAĞDAKİ elemanın sol ucuna verilir: düğüm i mafsallıysa açıklık i PF."""
    ortak = dict(EI=[1.0] * 3, supports=["pin", "roller", "roller", "roller"])
    assert BeamModel(spans=[4.0] * 3, hinges=[], **ortak).eletypes() == [1, 1, 1]
    assert BeamModel(spans=[4.0] * 3, hinges=[2], **ortak).eletypes() == [1, 3, 1]
    assert BeamModel(spans=[4.0] * 3, hinges=[2, 3], **ortak).eletypes() == [1, 3, 3]


def test_mafsal_dugum_dogrulama():
    """Mafsal yalnız ara düğüme konabilir; uç düğüm ve tekrar hata verir."""
    ortak = dict(spans=[6.0, 6.0], EI=[1.0, 1.0], supports=["pin", "roller", "pin"])
    assert BeamModel(hinges=[1], **ortak).validate()          # sol uç düğüm
    assert BeamModel(hinges=[3], **ortak).validate()          # sağ uç düğüm
    assert BeamModel(hinges=[2, 2], **ortak).validate()       # tekrar
    assert BeamModel(hinges=[2], **ortak).validate() == []    # geçerli


def test_mesnet_ustunde_mafsal_iki_basit_kirise_ayirir():
    """2×6 m, düğüm 2'de hem mesnet hem mafsal → iki bağımsız basit kiriş.

    Her açıklık ayrı ayrı basit kiriş gibi davranır: mesnet momenti 0,
    açıklık momenti wL²/8 = 90 kNm, tepkiler 60 / (60+60) / 60 kN.
    Sürekli kiriş çözümünden (test_referans_surekli_kiris) farklı olması,
    mafsalın gerçekten hesaba girdiğini gösterir.
    """
    model = BeamModel(
        spans=[6.0, 6.0], EI=[30_000.0] * 2,
        supports=["pin", "roller", "roller"],
        loads=[Load(1, "udl", [20.0]), Load(2, "udl", [20.0])],
        hinges=[2],
    )
    assert model.static_degree() == 0  # izostatik
    r = solve(model)
    assert r["Mmax"] == pytest.approx(90.0, rel=1e-3)
    assert r["Mmin"] == pytest.approx(0.0, abs=1e-6)
    assert _tepki(r, 1) == pytest.approx(60.0, rel=1e-4)
    assert _tepki(r, 2) == pytest.approx(120.0, rel=1e-4)
    assert _tepki(r, 3) == pytest.approx(60.0, rel=1e-4)


def test_gerber_konsol_asili_acilik():
    """Klasik Gerber: ankastre konsol + mafsalla asılan basit açıklık.

    Düğüm 1 ankastre, düğüm 2 mesnetsiz mafsal, düğüm 3 kayıcı. Yük yalnız
    2. açıklıkta (20 kN/m × 6 m). Asılan açıklık basit kiriş gibi çalışır:
    uçlara 60 kN gider. Mafsaldan gelen 60 kN konsolun ucuna etkir →
    ankastrede M = -60·6 = -360 kNm, düşey tepki 60 kN.
    """
    model = BeamModel(
        spans=[6.0, 6.0], EI=[30_000.0] * 2,
        supports=["fixed", "free", "roller"],
        loads=[Load(2, "udl", [20.0])],
        hinges=[2],
    )
    assert model.static_degree() == 0
    r = solve(model)
    assert _tepki(r, 1) == pytest.approx(60.0, rel=1e-4)
    assert _tepki(r, 3) == pytest.approx(60.0, rel=1e-4)
    assert r["Mmin"] == pytest.approx(-360.0, rel=1e-3)
    # Mafsalda moment sıfır olmalı (x = 6 m).
    i_mafsal = int((abs(r["x"] - 6.0)).argmin())
    assert r["M"][i_mafsal] == pytest.approx(0.0, abs=1e-6)


def test_fazla_mafsal_mekanizma_hatasi():
    """Mafsal sayısı mesnet tepkilerini aşınca anlaşılır SolverError gelir."""
    model = BeamModel(
        spans=[6.0, 6.0], EI=[30_000.0] * 2,
        supports=["pin", "roller", "free"],
        loads=[Load(1, "udl", [20.0])],
        hinges=[2],
    )
    assert model.static_degree() == -1
    with pytest.raises(SolverError, match="mekanizma"):
        solve(model)
