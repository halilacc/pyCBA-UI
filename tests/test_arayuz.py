"""Arayüz regresyon testleri — `streamlit.testing.v1.AppTest` ile, tarayıcısız.

`app.py` gerçekten çalıştırılır; sunum katmanındaki bir hatayı (istisna, sessizce
sıfırlanan widget durumu) yakalamanın en hızlı yolu budur. Çekirdek testleri
`test_core.py`'dedir — buraya yalnız SUNUM davranışı girer.

Çalıştırma:  .venv\\Scripts\\python.exe -m pytest -q
"""

import json
from pathlib import Path

import matplotlib
import pytest
from streamlit.testing.v1 import AppTest

matplotlib.use("Agg")  # şema testleri ekran istemesin
import matplotlib.pyplot as plt  # noqa: E402  (backend seçiminden sonra)

from core import BeamModel, Load, solve  # noqa: E402
from ui_cizim import ciz_sema  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")
YUK_EKLE = "FormSubmitter:yuk_ekle_form-➕ Yük ekle"
MAFSAL_EKLE = "FormSubmitter:mafsal_ekle_form-➕ Mafsal ekle"


def _uygulama() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception
    return at


def _yuk_ekle(at: AppTest, w: float, nonce: int) -> AppTest:
    """Kenar çubuğundaki formdan bir UDL ekle (alan anahtarı sayaca bağlı)."""
    at.sidebar.number_input(key=f"lv_udl_w_{nonce}").set_value(w)
    return at.sidebar.button(key=YUK_EKLE).click().run()


@pytest.mark.parametrize("eylem", ["yuk_ekle", "mafsal_ekle", "mafsal_sil"])
def test_kenar_cubugu_widget_durumu_rerun_da_korunur(eylem):
    """Kenar çubuğundaki ekleme/silme, ALTINDAKİ widget'ları sıfırlamamalı.

    Streamlit, bir çalıştırmada ÇİZİLMEYEN widget'ın durumunu siler. Ekleme
    bloğu `st.rerun()`u anında çağırdığında betik orada kesiliyor, ondan sonra
    gelen widget'lar (mesnet çökmesi alanları, "4. Görünüm" anahtarları) hiç
    çizilmiyor ve bir sonraki çalıştırmada VARSAYILANLARIYLA geri geliyordu:
    kullanıcı sehim grafiğini kapatıp yeni bir yük eklediğinde grafik kendiliğinden
    açılıyordu. Çözüm, rerun'ı kenar çubuğunun sonunda tek noktadan tetiklemek
    (`app.py`: `yeniden_calistir`). Bu test o kuralı üç ekleme/silme yolunda da
    denetler.
    """
    at = _uygulama()
    _yuk_ekle(at, 20.0, nonce=0)
    at.sidebar.toggle(key="goster_D").set_value(False).run()
    at.sidebar.number_input(key="cokme_0").set_value(3.0).run()
    if eylem != "yuk_ekle":
        at.sidebar.number_input(key="mh_a_1_6_0").set_value(2.0)
        at.sidebar.button(key=MAFSAL_EKLE).click().run()

    if eylem == "yuk_ekle":
        _yuk_ekle(at, 10.0, nonce=1)
        assert len(at.session_state["loads"]) == 2
    elif eylem == "mafsal_ekle":
        assert at.session_state["span_hinges"] == [(1, 2.0)]
    else:
        at.sidebar.button(key="mh_sil_0").click().run()
        assert at.session_state["span_hinges"] == []

    assert not at.exception
    assert at.sidebar.toggle(key="goster_D").value is False, "sehim anahtarı sıfırlandı"
    assert at.sidebar.number_input(key="cokme_0").value == 3.0, "çökme değeri sıfırlandı"


def test_yalniz_cokme_ile_sonuc_uretilir():
    """Yük olmadan, tek başına mesnet çökmesi de sonuç vermeli.

    İki eşit açıklıkta orta mesnet 10 mm çökerse M = 3EIδ/L² = 25 kNm
    (bkz. test_core.test_cokme_hiperstatik_kuvvet_yontemi). Kart metni sunum
    katmanının çökmeyi çözüme kadar taşıdığını doğrular.
    """
    at = _uygulama()
    at.sidebar.number_input(key="cokme_1").set_value(10.0).run()
    assert not at.exception
    kartlar = {m.label: m.value for m in at.metric}
    assert kartlar["Maks. moment [kNm]"] == "25.00"
    assert kartlar["Min. sehim [mm]"] == "-10.00"


def test_sema_olcegi_icerikten_etkilenmez():
    """Aynı kirişte çizim ölçeği (metre başına piksel) her içerikte aynı olmalı.

    PyCBA şemayı `adjustable="box"` ile eşit en-boy oranında çizer: düşey veri
    aralığı içerikle değiştiği için (tekil yük oku uzun, yukarı yük alta taşar,
    moment yayı, tepki okları var/yok) eksen kutusu daralıp genişliyor, punto
    cinsinden sabit olan yazı ve çizgi kalınlığı çizime göre 1.8 kata varan
    oranda büyüyüp küçülüyordu — kullanıcı "yazılar büyüdü, çizgiler
    kalınlaştı" diye görüyordu. `ui_cizim._sabitle_olcek` kutu genişliğini
    sabitleyip figür YÜKSEKLİĞİNİ türetir; ölçek yalnız kiriş uzunluğuna bağlı
    kalır. Yükseklik bilerek serbesttir, burada denetlenmez.
    """
    ortak = dict(spans=[6.0, 6.0, 6.0], EI=[30_000.0] * 3,
                 supports=["pin", "roller", "roller", "pin"])
    icerikler = {
        "yük yok": (BeamModel(**ortak), False),
        "UDL": (BeamModel(loads=[Load(i, "udl", [20.0]) for i in (1, 2, 3)],
                          **ortak), True),
        "tekil": (BeamModel(loads=[Load(2, "point", [50.0, 3.0])], **ortak), True),
        "yukarı": (BeamModel(loads=[Load(2, "udl", [-20.0])], **ortak), True),
        "moment": (BeamModel(loads=[Load(2, "moment", [50.0, 3.0])], **ortak), True),
        "çökme": (BeamModel(loads=[Load(1, "udl", [20.0])],
                            settlements={2: -0.01}, **ortak), True),
    }
    olcekler = {}
    for ad, (m, tepkili) in icerikler.items():
        sonuc = solve(m) if tepkili else None
        fig, ax = plt.subplots(figsize=(10, 3.4))
        try:
            ciz_sema(ax, m, sonuc["reactions"] if sonuc else None, "tr")
            fig.canvas.draw()
            kutu = ax.get_window_extent(fig.canvas.get_renderer())
            x0, x1 = ax.get_xlim()
            olcekler[ad] = kutu.width / (x1 - x0)  # metre başına piksel
        finally:
            plt.close(fig)
    ilk = next(iter(olcekler.values()))
    for ad, olcek in olcekler.items():
        assert olcek == pytest.approx(ilk, rel=1e-6), f"{ad}: ölçek kaymış ({olcekler})"


def test_sema_EI_den_etkilenmez():
    """EI değiştirmek şemayı DEĞİŞTİRMEMELİ — piksel piksel aynı kalmalı.

    PyCBA, açıklıkların EI'si farklı olduğu anda kirişi düz çizgi yerine
    derinliği EI^(1/3) ile değişen gri bir gövde olarak çiziyor; gövde ara
    mesnet gliflerini, düğüm harflerini ve çökme etiketlerini yutuyordu
    (bkz. ui_cizim.ciz_sema). Tepkiler EI'ye bağlı olduğu için karşılaştırma
    tepkisiz yapılır: geriye kalan her şey (geometri, yük, mesnet, çökme)
    EI'den bağımsızdır, dolayısıyla iki görüntü birebir eşit olmalıdır.
    """
    def _piksel(EI):
        m = BeamModel(
            spans=[6.0, 6.0, 6.0], EI=EI,
            supports=["pin", "roller", "roller", "pin"],
            loads=[Load(i, "udl", [20.0]) for i in (1, 2, 3)],
            settlements={2: -0.01},
        )
        fig, ax = plt.subplots(figsize=(10, 3.4))
        try:
            ciz_sema(ax, m, None, "tr")
            fig.canvas.draw()
            return bytes(fig.canvas.buffer_rgba())
        finally:
            plt.close(fig)

    assert _piksel([30_000.0] * 3) == _piksel([30_000.0, 90_000.0, 15_000.0])


@pytest.mark.parametrize("n_span", [1, 2, 3, 6, 8])
def test_sema_cokme_etiketleri_cakismaz(n_span):
    """Çökme etiketleri birbirine, düğüm harflerine ve eksen kenarına değmemeli.

    Etiket genişliği punto cinsinden sabit, mesnet arası ise açıklık sayısıyla
    daralır: üç açıklıkta etiketler karşı karşıya geliyor, altıda düğüm
    harflerinin (A, B, …) üstüne biniyordu. `ui_cizim.ciz_cokmeler` bunu iki
    satıra dağıtarak çözer; burada gerçekten çizdirip kutular ölçülür — göz
    kararı değil (bkz. CLAUDE.md "gece modu" bölümündeki aynı ilke).

    En sıkışık durum (10 açıklık) BİLEREK dışarıda: orada PyCBA'nın kendi tepki
    etiketleri de çakışıyor, şema zaten okunmuyor.
    """
    m = BeamModel(
        spans=[6.0] * n_span, EI=[30_000.0] * n_span,
        supports=["pin"] + ["roller"] * (n_span - 1) + ["pin"],
        loads=[Load(1, "udl", [20.0])],
        settlements={i + 1: -0.0125 * (i + 1) for i in range(n_span + 1)},
    )
    sonuc = solve(m)
    fig, ax = plt.subplots(figsize=(10, 3.4))
    try:
        ciz_sema(ax, m, sonuc["reactions"], "tr")
        fig.canvas.draw()
        ciz = fig.canvas.get_renderer()
        eksen = ax.get_window_extent(ciz)
        etiket = [t for t in ax.texts if t.get_text().startswith(("↓", "↑"))]
        harf = [t for t in ax.texts
                if len(t.get_text()) == 1 and t.get_text().isalpha()]
        assert len(etiket) == n_span + 1
        kutular = [t.get_window_extent(ciz) for t in etiket]

        for k, t in zip(kutular, etiket):
            assert eksen.x0 - 1 <= k.x0 and k.x1 <= eksen.x1 + 1, (
                f"{t.get_text()!r} eksen dışına taşıyor"
            )
        for i, a in enumerate(kutular):
            for b in kutular[i + 1:]:
                assert not (a.x1 > b.x0 and b.x1 > a.x0
                            and a.y1 > b.y0 and b.y1 > a.y0), "etiketler çakışıyor"
            for hb in (t.get_window_extent(ciz) for t in harf):
                assert not (a.x1 > hb.x0 and hb.x1 > a.x0
                            and a.y1 > hb.y0 and hb.y1 > a.y0), "etiket harfe biniyor"
    finally:
        plt.close(fig)


# ------------------------------------------------------------ zarf diyagramları
def test_zarf_bolumu_yalniz_anahtar_aciksa_gelir():
    """Zarf varsayılan olarak KAPALI; açılınca ayrı başlık ve kartlar eklenir.

    Zarf N+2 çözüm demek — kimse istemeden hesaplanmamalı. Açıldığında
    "Sonuçlar" bölümünün YERİNİ almaz, altına eklenir (sekme değil): ikisi de
    aynı anda görünür.
    """
    at = _uygulama()
    _yuk_ekle(at, 20.0, nonce=0)
    assert "Zarf diyagramları" not in [s.value for s in at.subheader]
    assert len(at.metric) == 3

    at.sidebar.toggle(key="zarf_ac").set_value(True).run()
    assert not at.exception
    basliklar = [s.value for s in at.subheader]
    assert "Sonuçlar" in basliklar and "Zarf diyagramları" in basliklar
    assert len(at.metric) == 6  # 3 kesit tesiri + 3 zarf kartı


def test_zarf_yuk_sinifi_formdan_gecer():
    """Ekleme formundaki sınıf seçimi modele ulaşmalı (varsayılan G)."""
    at = _uygulama()
    _yuk_ekle(at, 20.0, nonce=0)
    assert at.session_state["loads"][0].sinif == "G"

    at.sidebar.number_input(key="lv_udl_w_1").set_value(10.0)
    at.sidebar.radio(key="lv_sinif_1").set_value("Q")
    at.sidebar.button(key=YUK_EKLE).click().run()
    assert not at.exception
    assert [ld.sinif for ld in at.session_state["loads"]] == ["G", "Q"]


def test_zarf_birim_katsayilarda_tek_cozumle_ayni():
    """γ'ların hepsi 1 ise zarf, katsayısız tek çözümle aynı sayıyı vermeli.

    Kartların yan yana durduğu bir arayüzde en kolay yanlış anlaşılan şey,
    zarfın KATSAYILI yüklerle hesaplandığıdır; bu test katsayı yolunu (kenar
    çubuğundaki "Özel" seti) uçtan uca doğrular: katsayı 1'e çekilince iki
    bölümün sayıları örtüşür.
    """
    at = _uygulama()
    _yuk_ekle(at, 20.0, nonce=0)
    at.sidebar.toggle(key="zarf_ac").set_value(True).run()
    at.sidebar.selectbox(key="zarf_set").set_value("ozel").run()
    for anahtar in ("zarf.gG_maks", "zarf.gG_min", "zarf.gQ_maks", "zarf.gQ_min"):
        at.sidebar.number_input(key=f"gamma_{anahtar}").set_value(1.0)
    at.run()
    assert not at.exception
    sonuc = [(m.label, m.value) for m in at.metric[:3]]
    zarf = [(m.label, m.value) for m in at.metric[3:]]
    assert sonuc == zarf


def test_zarf_mesnet_kalkmasini_bildirir():
    """Hareketli yük komşu açıklığa alınınca kalkan mesnet uyarı vermeli.

    2×6 m, iki açıklıkta da Q: yalnız biri yüklüyken R_A = -7.5·γ_Q < 0.
    Tek çözümde (ikisi de yüklü) R_A pozitiftir, yani bu uyarı ancak zarfla
    doğar — ankraj ihtiyacını görünür kılan da odur.
    """
    at = _uygulama()
    at.session_state["loads"] = [Load(1, "udl", [20.0], "Q"),
                                 Load(2, "udl", [20.0], "Q")]
    at.sidebar.toggle(key="zarf_ac").set_value(True).run()
    assert not at.exception
    assert any("Mesnet kalkması" in w.value for w in at.warning), \
        [w.value for w in at.warning]


def test_zarf_bandi_alt_zarftan_doldurulur():
    """Taralı bant `fill="tonexty"` ile bir ÖNCEKİ ize kadar dolar.

    Yani her panelde ALT (min) zarf önce eklenmeli; izler ters sıraya girerse
    dolgu yanlış tarafa taşar ve bant "maksimumun üstü" gibi görünür. Figürün
    kendisi denetlenir — gözle değil. Moment ekseninin ters olması da kesit
    tesiri diyagramıyla aynı konvansiyonu koruduğunu gösterir.
    """
    at = _uygulama()
    at.session_state["loads"] = [Load(1, "udl", [20.0], "G"),
                                 Load(2, "udl", [10.0], "Q")]
    at.sidebar.toggle(key="zarf_ac").set_value(True).run()
    assert not at.exception
    spec = json.loads(at.get("plotly_chart")[1].proto.spec)
    assert [(iz.get("name"), iz.get("fill"), iz.get("yaxis"))
            for iz in spec["data"]] == [
        ("Kesme min.", None, "y"), ("Kesme maks.", "tonexty", "y"),
        ("Moment min.", None, "y2"), ("Moment maks.", "tonexty", "y2"),
        ("Sehim min.", None, "y3"), ("Sehim maks.", "tonexty", "y3"),
    ]
    assert spec["layout"]["yaxis2"]["autorange"] == "reversed"


def test_zarf_hareketli_yuk_yoksa_soyler():
    """Yalnız sabit yükle zarf anlamlıdır ama sınırlıdır — kullanıcıya söylenir."""
    at = _uygulama()
    _yuk_ekle(at, 20.0, nonce=0)
    at.sidebar.toggle(key="zarf_ac").set_value(True).run()
    assert not at.exception
    assert any("hareketli (Q) yük yok" in i.value for i in at.info), \
        [i.value for i in at.info]
