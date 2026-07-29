"""Çekirdek regresyon testleri — arayüzsüz, elle doğrulanabilir vakalar.

Buradaki her vaka ya kapalı formülle ya da klasik statik çözümle elde
edilmiştir; PyCBA'nın çıktısını "olduğu gibi" dondurmaz. Amaç, `core/`de bir
değişiklik yapıldığında bilinen doğru sonuçların bozulup bozulmadığını anında
görmek.

Çalıştırma:  .venv\\Scripts\\python.exe -m pytest -q
"""

from dataclasses import replace

import numpy as np
import pytest

from core import (
    BeamModel, Load, SolverError, kombinasyonlar, olcekli_model, solve,
    solve_envelope,
)
from core.axial import solve_axial

TOL = 1e-6  # bağıl tolerans (çözümler analitik; sayısal gürültü çok küçük)


def _tepki(sonuc, dugum):
    """1-tabanlı düğüm no'suna ait düşey tepkiyi döndür."""
    for r in sonuc["reactions"]:
        if r["node"] == dugum:
            return r["V"]
    raise AssertionError(f"Düğüm {dugum} için tepki yok")


def _N(sonuc, x):
    """N diyagramında x konumundaki değer(ler)i soldan sağa döndür.

    Diyagram eleman uçlarından kurulur, yani her iç düğüm dizide iki kez geçer.
    Tekil eksenel yükte bu iki değer FARKLIDIR (sıçrama); testler ikisini de
    görebilsin diye liste döner: [sol_değer, sağ_değer]. Kiriş uçlarında ve
    sıçramasız noktalarda tek/eşit değerler gelir.
    """
    xN, N = np.asarray(sonuc["xN"]), np.asarray(sonuc["N"])
    return [float(N[i]) for i in range(len(xN)) if abs(xN[i] - x) < 1e-9]


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


# ------------------------------------------------------- Gerber (açıklık içi mafsal)
def _gerber_20m():
    """Mesnetler x=0/10/20, 2. açıklığın 3. metresinde mafsal, 10 kN/m tam yük.

    El hesabı: sağ parça (13..20, 7 m) basit kiriş → uçlara 35 kN. Sol parça
    (0..13) pin@0 + roller@10, ucunda 35 kN: ΣM₀ ⇒ R₁₀ = (130·6,5 + 35·13)/10
    = 130 kN, ΣFy ⇒ R₀ = 35 kN. Mesnet üstü M(10) = −(35·3 + 30·1,5) = −150 kNm.
    """
    return BeamModel(
        spans=[10.0, 10.0], EI=[30_000.0] * 2,
        supports=["pin", "roller", "roller"],
        loads=[Load(1, "udl", [10.0]), Load(2, "udl", [10.0])],
        span_hinges=[(2, 3.0)],
    )


def test_aciklik_ici_mafsal_el_hesabi():
    model = _gerber_20m()
    assert model.validate() == []
    assert model.static_degree() == 0
    r = solve(model)
    assert _tepki(r, 1) == pytest.approx(35.0, rel=1e-4)
    assert _tepki(r, 2) == pytest.approx(130.0, rel=1e-4)
    assert _tepki(r, 3) == pytest.approx(35.0, rel=1e-4)
    i10 = int(abs(r["x"] - 10.0).argmin())
    i13 = int(abs(r["x"] - 13.0).argmin())
    assert r["M"][i10] == pytest.approx(-150.0, rel=1e-3)
    assert r["M"][i13] == pytest.approx(0.0, abs=1e-6)


def test_aciklik_ici_mafsal_elle_bolmeye_denk():
    """Otomatik bölme, kullanıcının elle böldüğü modelle aynı sonucu vermeli.

    Bu eşdeğerlik testi `expand()`in asıl güvencesidir: yük dağıtımı veya düğüm
    eşlemesi bozulursa iki model ayrışır.
    """
    elle = BeamModel(
        spans=[10.0, 3.0, 7.0], EI=[30_000.0] * 3,
        supports=["pin", "roller", "free", "roller"],
        loads=[Load(i, "udl", [10.0]) for i in (1, 2, 3)],
        hinges=[3],
    )
    r_oto, r_elle = solve(_gerber_20m()), solve(elle)
    for anahtar in ("Mmax", "Mmin", "Vmax", "Vmin", "Dmax", "Dmin"):
        assert r_oto[anahtar] == pytest.approx(r_elle[anahtar], rel=1e-9, abs=1e-9)
    assert [x["V"] for x in r_oto["reactions"]] == pytest.approx(
        [x["V"] for x in r_elle["reactions"]], rel=1e-9
    )
    # Düğüm no'ları KULLANICI numaralandırmasında kalmalı (1,2,3 — 4 değil).
    assert [x["node"] for x in r_oto["reactions"]] == [1, 2, 3]
    assert [x["node_expanded"] for x in r_oto["reactions"]] == [1, 2, 4]


@pytest.mark.parametrize(
    "kind, values",
    [
        ("point", [40.0, 7.0]),            # kesimin (a=4) sağında
        ("point", [40.0, 2.0]),            # kesimin solunda
        ("moment", [25.0, 8.0]),
        ("partial_udl", [12.0, 2.0, 5.0]),  # kesimi AŞIYOR → ikiye bölünmeli
        ("trapezoid", [6.0, 18.0, 0.0, 0.0]),   # tam açıklık trapez
        ("trapezoid", [6.0, 18.0, 1.0, 8.0]),   # kısmi trapez, kesimi aşıyor
    ],
)
def test_yuk_bolme_fiziksel_tutarli(kind, values):
    """Kesim noktasını aşan her yük tipi bölündükten sonra fizik korunmalı.

    2 açıklık (6+10), 2. açıklığın 4. metresinde mafsal; yük 2. açıklıkta.
    Ölçüt bilerek fizikseldir (beklenen sonucu `expand()`in kendi çıktısından
    türetmek döngüsel olurdu): mafsalda moment tam sıfır olmalı ve tepkiler
    toplamı uygulanan toplam düşey yüke eşit çıkmalı. Yük bölünürken şiddet
    veya uzunluk kaybolsa/çiftlense bu iki koşuldan biri bozulur.
    """
    model = BeamModel(
        spans=[6.0, 10.0], EI=[30_000.0] * 2,
        supports=["fixed", "roller", "roller"],
        loads=[Load(2, kind, list(values))],
        span_hinges=[(2, 4.0)],
    )
    assert model.validate() == []
    r = solve(model)
    # Mafsalda (x = 6 + 4 = 10 m) moment sıfır olmalı.
    i_h = int(abs(r["x"] - 10.0).argmin())
    assert r["M"][i_h] == pytest.approx(0.0, abs=1e-6)
    # Düşey denge: tepkiler toplamı = uygulanan toplam düşey yük.
    toplam_tepki = sum(x["V"] for x in r["reactions"] if x["V"] is not None)
    beklenen = {
        "point": lambda v: v[0],
        "moment": lambda v: 0.0,
        "partial_udl": lambda v: v[0] * v[2],
        "trapezoid": lambda v: (v[0] + v[1]) / 2 * (v[3] if v[3] else 10.0),
    }[kind](values)
    assert toplam_tepki == pytest.approx(beklenen, rel=1e-6, abs=1e-9)


def test_aciklik_ici_mafsal_konum_dogrulama():
    """Konum açıklığın içinde olmalı; uçlar ve açıklık dışı reddedilir."""
    ortak = dict(spans=[6.0, 6.0], EI=[1.0, 1.0], supports=["pin", "roller", "pin"])
    assert BeamModel(span_hinges=[(2, 0.0)], **ortak).validate()   # sol uç
    assert BeamModel(span_hinges=[(2, 6.0)], **ortak).validate()   # sağ uç
    assert BeamModel(span_hinges=[(2, 7.0)], **ortak).validate()   # açıklık dışı
    assert BeamModel(span_hinges=[(3, 1.0)], **ortak).validate()   # açıklık yok
    assert BeamModel(span_hinges=[(2, 3.0)], **ortak).validate() == []


def test_iki_mesnet_arasinda_mafsal_mekanizmadir():
    """6 m'lik tek açıklığın ortasına mafsal: iki çubuk + uçta mesnet = mekanizma.

    Fiziksel olarak çöker; çözücü bunu anlaşılır mesajla reddetmeli.
    """
    model = BeamModel(
        spans=[6.0], EI=[30_000.0], supports=["pin", "roller"],
        loads=[Load(1, "udl", [20.0])], span_hinges=[(1, 3.0)],
    )
    assert model.static_degree() == -1
    with pytest.raises(SolverError, match="mekanizma"):
        solve(model)


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


# ------------------------------------------------------- eksenel (normal kuvvet)
# İşaret kabulü (bkz. core/axial.py): yük +x sağa pozitif, N çekmede pozitif,
# yatay mesnet tepkisi H de +x yönünde pozitif — yani sağa iten +10 kN'lik yükü
# tek başına taşıyan mesnetin tepkisi −10 kN'dir.
def _eksenel(supports, loads, spans=(3.0, 3.0), **kw):
    return BeamModel(spans=list(spans), EI=[30_000.0] * len(spans),
                     supports=list(supports), loads=loads, **kw)


def test_eksenel_izostatik_tekil_yuk():
    """Tek yatay tutulu mesnet: N, yükün solunda P, sağında 0 (kapalı çözüm)."""
    m = _eksenel(["pin", "roller", "roller"], [Load(2, "axial_point", [10.0, 1.5])])
    r = solve(m)
    assert _N(r, 0.0) == pytest.approx([10.0])
    assert _N(r, 4.5) == pytest.approx([10.0, 0.0])   # yük noktasında sıçrama
    assert _N(r, 6.0) == pytest.approx([0.0])
    assert r["reactions"][0]["H"] == pytest.approx(-10.0, abs=1e-9)
    # Yatayda serbest mesnetlerde H sütunu boş kalmalı (0.0 değil None).
    assert r["reactions"][1]["H"] is None and r["reactions"][2]["H"] is None


def test_eksenel_hiperstatik_tekil_yuk():
    """İki pin arasında P: tepkiler uzunlukla ters orantılı (çubuk kapalı çözümü).

    L1=2, L2=4, x=1'de P=+12 → R_sol = −P·b/L = −10, R_sağ = −P·a/L = −2.
    Sabit EA varsayımı bu vakada sonucu etkilemez: paylaşım yalnız uzunluk
    oranına bağlıdır, dolayısıyla test EA=1 kabulünü değil çözümü sınar.
    """
    m = _eksenel(["pin", "roller", "pin"], [Load(1, "axial_point", [12.0, 1.0])],
                 spans=(2.0, 4.0))
    r = solve(m)
    assert r["reactions"][0]["H"] == pytest.approx(-10.0, rel=1e-9)
    assert r["reactions"][2]["H"] == pytest.approx(-2.0, rel=1e-9)
    assert _N(r, 1.0) == pytest.approx([10.0, -2.0])  # çekme → basınç


def test_eksenel_yayili_yuk_ucgen_diyagram():
    """n=+5 kN/m tüm kirişte, tek tutulu uç: N mesnette 30, serbest uçta 0."""
    m = _eksenel(["pin", "roller", "roller"],
                 [Load(1, "axial_udl", [5.0]), Load(2, "axial_udl", [5.0])])
    r = solve(m)
    assert _N(r, 0.0) == pytest.approx([30.0])
    assert _N(r, 3.0) == pytest.approx([15.0, 15.0])  # sürekli: sıçrama yok
    assert _N(r, 6.0) == pytest.approx([0.0], abs=1e-9)
    assert r["reactions"][0]["H"] == pytest.approx(-30.0, rel=1e-9)


def test_eksenel_basinc_isareti():
    """Sola (−) yük basınç üretir: N negatif, tepki pozitif (+x)."""
    m = _eksenel(["pin", "roller"], [Load(1, "axial_point", [-10.0, 1.5])],
                 spans=(3.0,))
    r = solve(m)
    assert r["Nmin"] == pytest.approx(-10.0, rel=1e-9)
    assert r["reactions"][0]["H"] == pytest.approx(10.0, rel=1e-9)


def test_eksenel_mafsal_normal_kuvveti_aktarir():
    """Mafsal MOMENT mafsalıdır: N diyagramını değiştirmemeli.

    Aynı eksenel yük, (a) mafsalsız, (b) açıklık içi mafsallı, (c) düğüm
    mafsallı modellerde aynı N'i vermeli. Mafsal eksenel serbestlik açarsa bu
    test kırılır.
    """
    yuk = [Load(2, "axial_point", [10.0, 1.5])]
    r_yok = solve(_eksenel(["pin", "roller", "roller"], list(yuk)))
    r_ic = solve(_eksenel(["pin", "roller", "roller"], list(yuk),
                          span_hinges=[(1, 1.5)]))
    r_dugum = solve(_eksenel(["fixed", "roller", "roller"], list(yuk), hinges=[2]))
    for r in (r_ic, r_dugum):
        assert _N(r, 4.5) == pytest.approx([10.0, 0.0])
        assert r["Nmax"] == pytest.approx(r_yok["Nmax"], rel=1e-9)
        assert r["reactions"][0]["H"] == pytest.approx(-10.0, rel=1e-9)


def test_eksenel_yuk_mesnet_uzerinde():
    """Yük tam yatay tutulu düğümde: mesnet tümünü alır, N her yerde sıfır."""
    m = _eksenel(["pin", "pin", "roller"], [Load(1, "axial_point", [10.0, 3.0])])
    r = solve(m)
    assert r["Nmax"] == pytest.approx(0.0, abs=1e-9)
    assert r["Nmin"] == pytest.approx(0.0, abs=1e-9)
    assert r["reactions"][1]["H"] == pytest.approx(-10.0, rel=1e-9)


def test_eksenel_yatay_mesnet_yoksa_hata():
    """Yalnız kayıcı mesnet varken eksenel yük mekanizmadır; anlaşılır hata gelir.

    Düşey sistem çözülebilir olduğu için hatayı `static_degree()` değil eksenel
    çözücü yakalar (PyCBA yatay DOF tutmaz).
    """
    m = _eksenel(["roller", "roller", "roller"],
                 [Load(1, "udl", [20.0]), Load(1, "axial_point", [10.0, 1.5])])
    with pytest.raises(SolverError, match="yatayda tutulu mesnet yok"):
        solve(m)


def test_eksenel_yuk_dusey_sonuclari_etkilemez():
    """Birinci mertebe teoride eksenel yük M/V/D'yi değiştirmez.

    Referans problem (2×6 m, 20 kN/m) üzerine eksenel yük eklendiğinde eğilme
    sonuçları birebir aynı kalmalı — eksenel yükün yanlışlıkla PyCBA'nın LM
    matrisine sızması bu testi kırar.
    """
    dusey = [Load(1, "udl", [20.0]), Load(2, "udl", [20.0])]
    r_saf = solve(_eksenel(["pin", "roller", "pin"], list(dusey), spans=(6.0, 6.0)))
    r_eks = solve(_eksenel(["pin", "roller", "pin"],
                           dusey + [Load(1, "axial_point", [50.0, 3.0])],
                           spans=(6.0, 6.0)))
    for anahtar in ("Mmax", "Mmin", "Vmax", "Vmin", "Dmax", "Dmin"):
        assert r_eks[anahtar] == pytest.approx(r_saf[anahtar], rel=1e-12, abs=1e-12)
    # İki uç pin olduğundan eksenel sistem hiperstatiktir: P=50, a=3, b=9,
    # L=12 → sol parçada N = P·b/L = 37,5 kN çekme.
    assert r_eks["Nmax"] == pytest.approx(37.5, rel=1e-9)


def test_eksenel_yuk_yokken_diyagram_sifir():
    """Eksenel yük yoksa N sıfır, tutulu düğümlerde H sıfır (hata değil)."""
    m = _eksenel(["pin", "roller", "pin"], [Load(1, "udl", [20.0])])
    ax = solve_axial(m)
    assert np.allclose(ax["N"], 0.0)
    assert ax["H"] == {1: 0.0, 3: 0.0}


@pytest.mark.parametrize("EI, supports, bekleniyor", [
    # Hiperstatik eksenel sistem (iki pin) + farklı kesit → paylaşım EA'ya bağlı.
    ([30_000.0, 120_000.0], ["pin", "roller", "pin"], True),
    ([30_000.0, 30_000.0], ["pin", "roller", "pin"], False),   # prizmatik: kesin
    ([30_000.0, 120_000.0], ["pin", "roller", "roller"], False),  # izostatik: kesin
])
def test_ea_uyari_bayragi(EI, supports, bekleniyor):
    """EA=1 varsayımı yalnız hiperstatik + farklı kesitte sonucu etkiler.

    Çözücü bunu `ea_uyari` ile bildirir; sunum katmanı uyarıyı buna bakarak
    gösterir. Diğer iki durumda sonuç EA'dan bağımsız kesindir, uyarı çıkmamalı.
    """
    m = BeamModel(spans=[6.0, 6.0], EI=EI, supports=supports,
                  loads=[Load(1, "axial_point", [100.0, 3.0])])
    assert solve(m)["ea_uyari"] is bekleniyor


# ------------------------------------------------------------------ mesnet çökmesi
def test_cokme_izostatikte_kesit_tesiri_uretmez():
    """Basit kirişte sağ mesnedin çökmesi rijit dönmedir: M = V = 0.

    İzostatik sistemde dayatılan yer değiştirme zorlanma doğurmaz; kiriş
    sadece döner. Sehim uçta tam çökme kadar, diğer uçta sıfırdır.
    """
    m = BeamModel(spans=[6.0], EI=[30_000.0], supports=["pin", "roller"],
                  settlements={2: -0.01})
    assert m.validate() == []
    r = solve(m)
    assert np.allclose(r["M"], 0.0, atol=1e-9)
    assert np.allclose(r["V"], 0.0, atol=1e-9)
    assert r["D"][0] == pytest.approx(0.0, abs=1e-12)
    assert r["D"][-1] == pytest.approx(-0.01, rel=1e-9)
    assert not r["reactions"][0]["V"]  # tepki de sıfır (yalnız rijit hareket)


def test_cokme_hiperstatik_kuvvet_yontemi():
    """İki eşit açıklıkta orta mesnet δ kadar çökerse (yüksüz kiriş).

    Kuvvet yöntemi: orta mesnet kaldırılınca 2L açıklıklı basit kiriş kalır,
    ortadaki birim kuvvetin esnekliği (2L)³/48EI = L³/6EI. Uyum denklemi
    R·L³/(6EI) = δ verir; yani orta mesnet AŞAĞI doğru 6EIδ/L³ çeker, uçlar
    3EIδ/L³ yukarı iter ve orta mesnette M = +3EIδ/L² (sağlama: P=6EIδ/L³
    tekil yüklü 2L basit kirişte M_orta = P·2L/4).
    """
    L, EI, delta = 6.0, 30_000.0, 0.01
    m = BeamModel(spans=[L, L], EI=[EI, EI],
                  supports=["pin", "roller", "roller"],
                  settlements={2: -delta})
    r = solve(m)
    assert _tepki(r, 1) == pytest.approx(3 * EI * delta / L**3, rel=1e-6)
    assert _tepki(r, 2) == pytest.approx(-6 * EI * delta / L**3, rel=1e-6)
    assert _tepki(r, 3) == pytest.approx(3 * EI * delta / L**3, rel=1e-6)
    assert r["Mmax"] == pytest.approx(3 * EI * delta / L**2, rel=1e-6)
    assert r["Dmin"] == pytest.approx(-delta, rel=1e-6)


def test_cokme_ustuste_toplama():
    """Çökme + yük, ayrı ayrı çözümlerin toplamına eşit olmalı (lineer sistem)."""
    ortak = dict(spans=[6.0, 6.0], EI=[30_000.0] * 2,
                 supports=["pin", "roller", "pin"])
    yuk = [Load(1, "udl", [20.0]), Load(2, "udl", [20.0])]
    r_yuk = solve(BeamModel(loads=yuk, **ortak))
    r_cokme = solve(BeamModel(settlements={2: -0.01}, **ortak))
    r_ikisi = solve(BeamModel(loads=yuk, settlements={2: -0.01}, **ortak))
    assert np.allclose(r_ikisi["M"], r_yuk["M"] + r_cokme["M"], atol=1e-6)
    assert np.allclose(r_ikisi["D"], r_yuk["D"] + r_cokme["D"], atol=1e-12)


def test_cokme_aciklik_ici_mafsalla_dogru_dugume_tasinir():
    """`expand()` çökmeyi de yeni düğüm numaralandırmasına taşımalı.

    1. açıklık a=3'te bölününce düğümler 1,(yeni),2,3 olur; kullanıcının 3.
    düğümüne verdiği çökme genişletilmiş modelde 4. düğüme düşer.
    """
    m = BeamModel(spans=[6.0, 6.0], EI=[30_000.0] * 2,
                  supports=["fixed", "roller", "roller"],
                  span_hinges=[(1, 3.0)], settlements={3: -0.01})
    genis, node_map = m.expand()
    assert node_map == [1, None, 2, 3]
    assert genis.settlements == {4: -0.01}
    # Tepki, kullanıcının düğüm numarasıyla geri gelir ve çökme oradadır.
    r = solve(m)
    assert min(rr["node"] for rr in r["reactions"]) == 1
    # Tolerans gevşek: PyCBA eleman sehimini eğrilikten SAYISAL integralle
    # (npts=100 yamuk) kurar, uzak uçta ~1e-5 bağıl hata birikir.
    assert r["D"][-1] == pytest.approx(-0.01, rel=1e-4)


@pytest.mark.parametrize("settlements, parca", [
    ({5: -0.01}, "düğüm no 5"),      # düğüm yok
    ({2: -0.01}, "serbest"),         # mesnetsiz düğüm
    ({1: float("nan")}, "sonlu"),    # sayısal olmayan değer
])
def test_cokme_dogrulama_hatalari(settlements, parca):
    """Geçersiz çökme tanımları doğrulamada anlaşılır mesaj vermeli."""
    m = BeamModel(spans=[6.0], EI=[30_000.0], supports=["fixed", "free"],
                  settlements=settlements)
    hatalar = m.validate()
    assert any(parca in h for h in hatalar), hatalar


def test_sehim_dizisinde_eleman_ucu_bosluk_yok():
    """PyCBA'nın uç dolgu istasyonları sehimde sıfır kalmamalı.

    `results.py` sehimi yalnız iç ızgaraya yazar; dolgu girdileri 0 kalır ve
    çöken mesnette / açıklık içi mafsalın serbest düğümünde sehim eğrisi oraya
    "düşüyor" gibi görünürdü (bkz. solver._sehim_dizisi). Aynı x'teki değerler
    birbirine eşit olmalı — tam değil, çünkü eleman sehimi eğrilikten SAYISAL
    integralle kurulur ve komşu elemanların uç değerleri arasında yamuk kuralı
    hatası (~1e-5 bağıl) kalır. Dolgu kusuru bunun 50 katı büyüklükteydi.
    """
    m = BeamModel(spans=[6.0, 6.0], EI=[30_000.0] * 2,
                  supports=["fixed", "free", "pin"],
                  loads=[Load(1, "udl", [20.0]), Load(2, "udl", [20.0])],
                  span_hinges=[(1, 4.0)])
    r = solve(m)
    x, D = np.asarray(r["x"]), np.asarray(r["D"])
    olcek = float(np.abs(D).max())
    for xi in np.unique(x):
        degerler = D[np.abs(x - xi) < 1e-12]
        assert np.ptp(degerler) < 1e-4 * olcek, f"x={xi} m'de sehim sıçraması var"


# ------------------------------------------------- yük düzenleri / zarf (core/zarf.py)
def _zarf_modeli(g=20.0, q=10.0, spans=(6.0, 6.0), supports=("pin", "pin", "pin")):
    """Her açıklığında g (sabit) ve q (hareketli) UDL bulunan kiriş."""
    n = len(spans)
    yukler = [Load(i + 1, "udl", [g], "G") for i in range(n)]
    if q:
        yukler += [Load(i + 1, "udl", [q], "Q") for i in range(n)]
    return BeamModel(spans=list(spans), EI=[30_000.0] * n,
                     supports=list(supports), loads=yukler)


def test_zarf_analitik_iki_aciklik():
    """2×6 m, G=20 + Q=10 kN/m, γ=(1, 1, 1, 0) — kapalı çözümle doğrulanır.

    İki eşit açıklıkta (uçlar mafsallı) UDL'ler w1, w2 için üç-moment
    denkleminden M_B = -(w1 + w2)·L²/16.
      · "tüm" düzeni  (w1 = w2 = 30) → M_B = -135 kNm  (zarfın minimumu)
      · "tek" düzeni  (w1 = 30, w2 = 20) → M_B = -112.5, R_A = 30·3 - 112.5/6
        = 71.25 kN; açıklık momenti x = R_A/w1 = 2.375 m'de tepe yapar ve
        M = R_A²/(2w1) = 84.609 kNm olur — zarfın maksimumu budur.
    "Hepsi yüklü" varsayan biri açıklıkta 84.6 yerine 50.6·1.5 = 75.9 görürdü.
    """
    z = solve_envelope(_zarf_modeli(), katsayilar=(1.0, 1.0, 1.0, 0.0))
    e_maks, e_min = z["ekstrem"]["Mmax"], z["ekstrem"]["Mmin"]
    # İstasyon ızgarası (açıklık başına 100 aralık) tam 2.375 m'ye düşmez.
    assert e_maks["deger"] == pytest.approx(84.609, abs=0.05)
    assert e_maks["x"] == pytest.approx(2.375, abs=0.06)
    assert e_maks["duzen"].anahtar == "tek"
    assert e_min["deger"] == pytest.approx(-135.0, rel=1e-4)
    assert e_min["x"] == pytest.approx(6.0, abs=1e-9)
    assert e_min["duzen"].anahtar == "tum"
    # Zarf her kesitte kendi düzeninin sonucunu sarmalı.
    assert np.all(z["Mmax"] >= z["Mmin"] - 1e-9)


def test_zarf_mesnet_kalkmasini_yakalar():
    """Yalnız 2. açıklık yüklüyken R_A = -7.5 kN (mesnet kalkar).

    M_B = -(0 + 20)·36/16 = -45 kNm, R_A = M_B/L = -7.5 kN. Tek bir "hepsi
    yüklü" çözümünde R_A = +45 kN çıkar ve ankraj ihtiyacı hiç görünmez.
    """
    m = BeamModel(spans=[6.0, 6.0], EI=[30_000.0] * 2,
                  supports=["pin", "pin", "pin"],
                  loads=[Load(1, "udl", [20.0], "Q"), Load(2, "udl", [20.0], "Q")])
    z = solve_envelope(m, katsayilar=(1.0, 1.0, 1.0, 0.0))
    dugum1 = z["reactions"][0]
    assert dugum1["node"] == 1
    assert dugum1["Vmin"] == pytest.approx(-7.5, rel=1e-4)
    assert dugum1["Vmin_duzen"].anahtar == "cift"  # yalnız 2. açıklık yüklü
    # "tek" düzeni (yalnız 1. açıklık): R_A = wL/2 + M_B/L = 60 - 7.5 = 52.5 kN
    assert dugum1["Vmax"] == pytest.approx(52.5, rel=1e-4)
    assert dugum1["Vmax_duzen"].anahtar == "tek"


@pytest.mark.parametrize("spans, supports", [
    ([6.0, 6.0], ["pin", "pin", "pin"]),
    ([5.0, 7.0, 6.0], ["pin", "pin", "pin", "pin"]),
    ([4.0, 6.0, 3.0], ["fixed", "pin", "pin", "free"]),  # ankastre + konsol
])
def test_zarf_pycba_load_pattern_ile_ayni(spans, supports):
    """Kendi zarfımız PyCBA `LoadPattern` ile BİREBİR aynı M/V vermeli.

    Zarfı kendimiz hesaplıyoruz (sehim zarfı, kullanıcı düğüm numarası ve
    Gerber uyumu için — bkz. core/zarf.py); bu test, o kazanımların sayısal bir
    sapma pahasına gelmediğini garanti eder. Katsayılar Eurocode.
    """
    import pycba as cba

    g, q, kats = 20.0, 10.0, (1.35, 1.00, 1.50, 0.00)
    n = len(spans)
    EI = [30_000.0] * n
    z = solve_envelope(_zarf_modeli(g, q, spans, supports), katsayilar=kats)

    lp = cba.LoadPattern(cba.BeamAnalysis(L=spans, EI=EI, supports=supports, LM=None))
    lp.set_dead_loads([[i + 1, 1, g, 0, 0] for i in range(n)], kats[0], kats[1])
    lp.set_live_loads([[i + 1, 1, q, 0, 0] for i in range(n)], kats[2], kats[3])
    env = lp.analyze()

    assert np.allclose(env.x, z["x"])
    for ad in ("Mmax", "Mmin", "Vmax", "Vmin"):
        assert np.allclose(getattr(env, ad), z[ad], atol=1e-9), ad


def test_zarf_sifira_kenetlenir():
    """Konsolda M hiçbir kesitte pozitif değil: `Mmax` sıfıra kenetlenir.

    PyCBA geleneği korunuyor (`results.py:468` zarfı sıfır dizisiyle başlatır):
    zarf ekseni sarar, `Mmax >= 0` ve `Mmin <= 0` her zaman doğrudur. Ankastre
    uçta gerçek moment −180 kNm'dir ve `Mmin`de görünür; `Mmax` orada 0 kalır.
    """
    m = BeamModel(spans=[4.0], EI=[30_000.0], supports=["fixed", "free"],
                  loads=[Load(1, "udl", [10.0], "Q")])
    z = solve_envelope(m, katsayilar=(1.35, 1.0, 1.5, 0.0))
    assert np.all(z["Mmax"] == 0.0)          # hiçbir düzende pozitif moment yok
    assert np.all(z["Mmin"] <= 1e-9)
    i_ank = int(np.argmin(z["Mmin"]))        # ankastre uç
    assert z["Mmin"][i_ank] == pytest.approx(-1.5 * 10.0 * 16 / 2, rel=1e-4)
    assert z["Mmax"][i_ank] == 0.0           # kenetleme: gerçek değer negatif
    assert z["ekstrem"]["Mmax"]["deger"] == 0.0
    assert z["ekstrem"]["Mmin"]["duzen"] is not None
    assert z["ekstrem"]["Mmin"]["x"] == pytest.approx(0.0, abs=1e-9)


def test_zarf_duzenleri_kullanici_acikliklarina_gore_kurulur():
    """Açıklık içi mafsal düzen SAYISINI değiştirmemeli.

    PyCBA patternlemeyi genişletilmiş açıklıklara uygular: 2 açıklıklı bir
    kirişte açıklık içi mafsal 3 açıklık gösterip 5 düzen üretir ve "tek/çift
    açıklıklar" kullanıcının numaralandırmasıyla örtüşmez. Bizde düzenler
    kullanıcı açıklıkları üzerinde kurulur, bölme her düzenin İÇİNDE yapılır.
    """
    kats = (1.35, 1.0, 1.5, 0.0)
    m = _zarf_modeli()  # 2 açıklık -> tum / tek / cift
    m_mafsal = BeamModel(spans=[6.0, 6.0], EI=[30_000.0] * 2,
                         supports=["fixed", "free", "pin"],
                         span_hinges=[(1, 4.0)],
                         loads=list(m.loads))
    assert [d.anahtar for d in kombinasyonlar(m, kats)] == ["tum", "tek", "cift"]
    assert ([d.spans for d in kombinasyonlar(m_mafsal, kats)]
            == [(1, 2), (1,), (2,)])
    z = solve_envelope(m_mafsal, katsayilar=kats)
    assert len(z["kombinasyonlar"]) == 3
    # Genişletme çözümün içinde: tepkiler kullanıcı düğüm no'suyla döner
    # (mafsalın doğurduğu serbest düğüm tepki listesine girmez).
    assert [r["node"] for r in z["reactions"]] == [1, 3]


def test_zarf_cokmeyi_her_duzende_korur():
    """Çökme kalıcı etkidir: patternlenmez, katsayı yemez, her düzende durur."""
    kats = (1.35, 1.0, 1.5, 0.0)
    m = _zarf_modeli()
    m_cokme = replace(m, settlements={2: -0.02})
    for d in kombinasyonlar(m_cokme, kats):
        assert olcekli_model(m_cokme, d, kats).settlements == {2: -0.02}
    # Çökme sonucu gerçekten etkiliyor (sessizce düşmüyor): hiperstatik sistemde
    # mesnet çökmesi moment doğurur, zarf da bunu görmeli.
    z, z_cokme = solve_envelope(m, kats), solve_envelope(m_cokme, kats)
    assert not np.allclose(z["Mmin"], z_cokme["Mmin"])


def test_zarf_ayirt_edilemeyen_katsayilarda_tek_duzen():
    """γ'lar yükleri ayırt etmiyorsa bütün düzenler aynıdır — bir kez çözülür."""
    sabit = _zarf_modeli(q=0.0)  # yalnız G
    assert len(kombinasyonlar(sabit, (1.0, 1.0, 1.5, 0.0))) == 1
    # γ_G,maks ≠ γ_G,min: sabit yükün kendisi de patternlenir, düzenler geri gelir.
    assert len(kombinasyonlar(sabit, (1.35, 1.0, 1.5, 0.0))) == 3
    assert len(kombinasyonlar(_zarf_modeli(), (1.0, 1.0, 1.5, 0.0))) == 3
    z = solve_envelope(sabit, katsayilar=(1.0, 1.0, 1.5, 0.0))
    assert z["hareketli_var"] is False
    # Tek düzen: zarfın iki ucu da aynı çözümü sarar (sıfır kenetlemesi dışında).
    r = solve(sabit)
    assert np.allclose(z["Mmin"], np.minimum(r["M"], 0.0))


def test_zarf_yuk_olcekleme_konumlari_bozmaz():
    """`Load.scaled` yalnız ŞİDDETİ çarpar; a/c konumları olduğu gibi kalır."""
    trapez = Load(2, "trapezoid", [10.0, 20.0, 1.5, 3.0], "Q").scaled(1.5)
    assert trapez.values == [15.0, 30.0, 1.5, 3.0]
    assert (trapez.span, trapez.kind, trapez.sinif) == (2, "trapezoid", "Q")
    tekil = Load(1, "point", [40.0, 2.0], "Q").scaled(0.0)
    assert tekil.values == [0.0, 2.0]  # yük sıfırlanır, konumu korunur


def test_zarf_yuk_sinifi_dogrulamasi():
    """Bilinmeyen sınıf ve hareketli (Q) eksenel yük anlaşılır hata vermeli."""
    m = BeamModel(spans=[6.0], EI=[30_000.0], supports=["fixed", "free"],
                  loads=[Load(1, "udl", [10.0], "H")])
    assert any("'H'" in h for h in m.validate()), m.validate()
    m2 = BeamModel(spans=[6.0], EI=[30_000.0], supports=["fixed", "free"],
                   loads=[Load(1, "axial_udl", [10.0], "Q")])
    assert any("eksenel" in h.lower() for h in m2.validate()), m2.validate()


# ------------------------------------------------------------------ hata yolları
def test_ara_dugumde_ankastre_mesnet():
    """Ankastre-mafsallı kiriş: yalnız 1. açıklıkta UDL (kapalı çözüm).

    `_map_reactions`ın en riskli dalı — ankastre UÇTA değil, ara düğümde.
    Sağdaki açıklık yüksüz ve sağ ucu kayıcı olduğunda 2. açıklık kuvvet
    taşımaz; sistem tek açıklıklı ankastre-mafsallı kirişe indirgenir:
    R_sol = 3wL/8 = 45, R_ankastre = 5wL/8 = 75, M_ankastre = wL²/8 = 90.
    """
    m = BeamModel(spans=[6.0, 6.0], EI=[30_000.0] * 2,
                  supports=["pin", "fixed", "roller"],
                  loads=[Load(1, "udl", [20.0])])
    r = solve(m)
    assert _tepki(r, 1) == pytest.approx(45.0, rel=1e-4)
    assert _tepki(r, 2) == pytest.approx(75.0, rel=1e-4)
    assert _tepki(r, 3) == pytest.approx(0.0, abs=1e-6)
    # Moment tepkisinin DEĞERİ: yalnız ankastre düğümde dolu olmalı.
    momentler = {x["node"]: x["M"] for x in r["reactions"]}
    assert momentler[1] is None and momentler[3] is None
    assert abs(momentler[2]) == pytest.approx(90.0, rel=1e-4)


def test_kararsiz_sistem_temiz_mesaj():
    """Mekanizma sayımının kaçırdığı düzen PyCBA'nın kararsızlık denetimine düşer.

    O denetimin ham metni İngilizcedir ve kullanıcıya `check_stability=False`
    önerir; çözücü bunu `is_stable()` ile önden yakalayıp kendi mesajını verir.
    (`np.linalg.LinAlgError` ayrı bir except dalında YAKALANAMAZ: numpy'da
    ValueError'ın alt sınıfıdır — bu test o dalın geri gelmesini de engeller.)
    """
    m = BeamModel(spans=[6.0, 6.0], EI=[30_000.0] * 2,
                  supports=["pin", "fixed", "free"],
                  loads=[Load(1, "udl", [20.0])], hinges=[2])
    assert m.static_degree() >= 0  # derece sayımı bu düzeni mekanizma saymaz
    for dil, parca in (("tr", "kararsız"), ("en", "unstable")):
        with pytest.raises(SolverError) as e:
            solve(m, dil)
        assert parca in str(e.value)
        assert "check_stability" not in str(e.value)


def test_gecersiz_model_solverror_verir():
    """`solve()` doğrulamayı kendisi yapar; ham ValueError sızmamalı.

    `hinges=[5]` iki açıklıklı kirişte geçersiz. `span_hinges` doluyken bu,
    expand() içinde anlaşılmaz bir `list.index(x): x not in list` hatasına
    dönüşüyordu — arayüz validate()'i önce çağırdığı için görünmüyordu ama
    `core/` tek başına da doğru davranmalı.
    """
    m = BeamModel(spans=[6.0, 6.0], EI=[30_000.0] * 2,
                  supports=["pin", "roller", "roller"],
                  loads=[Load(1, "udl", [20.0])],
                  hinges=[5], span_hinges=[(1, 3.0)])
    with pytest.raises(SolverError, match="Mafsal düğüm no 5"):
        solve(m)


def test_konum_hatasi_mekanizma_diye_bildirilmez():
    """Açıklık dışı mafsal konumu, konum hatası olarak raporlanmalı.

    Doğrulama olmadan expand() `spans=[9, -3]` üretiyor ve kullanıcı "mesnet
    ekleyin" tavsiyesi alıyordu; asıl sorun konumdur.
    """
    m = BeamModel(spans=[6.0, 6.0], EI=[30_000.0] * 2,
                  supports=["pin", "roller", "roller"],
                  loads=[Load(1, "udl", [20.0])], span_hinges=[(1, 9.0)])
    with pytest.raises(SolverError) as e:
        solve(m, "en")
    assert "Hinge position" in str(e.value)
    assert "mechanism" not in str(e.value)
