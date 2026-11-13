"""Kiriş şeması regresyon testleri (ciz_sema) — tarayıcısız, matplotlib Agg.

Çekirdek testleri `test_core.py`'dedir; API testleri `test_api.py`'dedir. Buraya
yalnız ŞEMA ÇİZİMİNİN davranışı girer (harflenme, ölçek, EI bağımsızlığı).
"""

import matplotlib
import pytest

matplotlib.use("Agg")  # şema testleri ekran istemesin
import matplotlib.pyplot as plt  # noqa: E402  (backend seçiminden sonra)

from core import BeamModel, Load, solve  # noqa: E402
from ui_cizim import ciz_sema  # noqa: E402


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
    kararı değil.

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
