"""Çekirdek regresyon testleri — arayüzsüz, elle doğrulanabilir vakalar.

Buradaki her vaka ya kapalı formülle ya da klasik statik çözümle elde
edilmiştir; PyCBA'nın çıktısını "olduğu gibi" dondurmaz. Amaç, `core/`de bir
değişiklik yapıldığında bilinen doğru sonuçların bozulup bozulmadığını anında
görmek.

Çalıştırma:  .venv\\Scripts\\python.exe -m pytest -q
"""

import numpy as np
import pytest

from core import BeamModel, Load, SolverError, solve
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
