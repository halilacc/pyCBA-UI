"""Arayüz regresyon testleri — `streamlit.testing.v1.AppTest` ile, tarayıcısız.

`app.py` gerçekten çalıştırılır; sunum katmanındaki bir hatayı (istisna, sessizce
sıfırlanan widget durumu) yakalamanın en hızlı yolu budur. Çekirdek testleri
`test_core.py`'dedir — buraya yalnız SUNUM davranışı girer.

Çalıştırma:  .venv\\Scripts\\python.exe -m pytest -q
"""

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


def test_yay_mesnet_arayuzden_uctan_uca():
    """Mesnet tipi "yay" seçilince katsayı alanı çıkmalı ve tepki tabloya girmeli.

    Asıl denetlenen: PyCBA yay kuvvetini tepki vektöründe (`R`) DEĞİL ayrı bir
    vektörde (`Rs`) verir; sunum katmanına yanlış eşlenirse tablodaki tepkiler
    kayar. Beklenen değer çekirdekten alınıp tablonun HTML'inde aranır.
    """
    at = _uygulama()
    _yuk_ekle(at, 20.0, nonce=0)
    assert "yay_1" not in [w.key for w in at.sidebar.number_input], \
        "yay katsayısı alanı, tip yay seçilmeden çizildi"
    at.sidebar.selectbox(key="sup_1").set_value("spring").run()
    at.sidebar.number_input(key="yay_1").set_value(1_000.0).run()
    assert not at.exception

    m = BeamModel(spans=[6.0, 6.0], EI=[30_000.0] * 2,
                  supports=["pin", "spring", "pin"], springs={2: 1_000.0},
                  loads=[Load(1, "udl", [20.0])])
    tepkiler = {r["node"]: r["V"] for r in solve(m)["reactions"]}
    assert sum(tepkiler.values()) == pytest.approx(120.0, rel=1e-9)  # denge
    html = " ".join(md.value for md in at.markdown)
    for dugum, V in tepkiler.items():
        assert f"{V:.3f}" in html, f"düğüm {dugum} tepkisi ({V:.3f}) tabloda yok"


def test_sema_yay_mesnedi_cizer():
    """Şema yay glifini çizmeli ve düğüm harflerini kaydırmamalı.

    `ciz_sema` glif listesini model tiplerinden kurar; "spring" adı PyCBA'nın
    kendi glif sabitiyle (render.SPRING) birebir aynı olduğu için yay doğrudan
    çizilir. Yay ÇİZİLEN bir mesnettir: harflenmede atlanırsa (free gibi)
    tepki tablosuyla eşleşme bozulur.
    """
    m = BeamModel(spans=[6.0, 6.0], EI=[30_000.0] * 2,
                  supports=["pin", "spring", "pin"], springs={2: 1_000.0},
                  loads=[Load(1, "udl", [20.0])])
    fig, ax = plt.subplots(figsize=(10, 3.4))
    try:
        ciz_sema(ax, m, solve(m)["reactions"], "tr")
        harfler = sorted(t.get_text() for t in ax.texts
                         if len(t.get_text()) == 1 and t.get_text().isalpha())
        assert harfler == ["A", "B", "C"]
    finally:
        plt.close(fig)


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
