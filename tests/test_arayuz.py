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
