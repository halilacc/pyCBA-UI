"""Dil kataloğu bütünlük testleri.

Çeviri hatası çalışma zamanında ortaya çıkar (eksik anahtar → sessizce Türkçeye
düşme, uyuşmayan `{alan}` → KeyError). Bu testler iki kataloğu da (arayüz +
çekirdek) statik olarak karşılaştırıp bu iki sınıfı ekleme anında yakalar.
"""

import string

import pytest

from core import LOAD_TYPES, SUPPORT_TYPES, BeamModel, Load, solve
from core import mesajlar
import ui_dil

# (ad, {dil: {anahtar: metin}}) — her iki katalog aynı kurallara tabi.
KATALOGLAR = [("ui_dil", ui_dil.METINLER), ("core.mesajlar", mesajlar.KATALOG)]


def _alanlar(sablon: str) -> set:
    """Bir format şablonundaki alan adları ({a:g} → "a")."""
    return {ad for _, ad, _, _ in string.Formatter().parse(sablon) if ad}


@pytest.mark.parametrize("ad, katalog", KATALOGLAR, ids=[k[0] for k in KATALOGLAR])
def test_diller_ayni_anahtarlari_icerir(ad, katalog):
    """Her dil aynı anahtar kümesini taşımalı — eksik çeviri sessizce TR'ye düşer."""
    tr, en = set(katalog["tr"]), set(katalog["en"])
    assert tr - en == set(), f"{ad}: İngilizcede eksik anahtarlar"
    assert en - tr == set(), f"{ad}: Türkçede karşılığı olmayan anahtarlar"


@pytest.mark.parametrize("ad, katalog", KATALOGLAR, ids=[k[0] for k in KATALOGLAR])
def test_format_alanlari_dillerde_ayni(ad, katalog):
    """Aynı anahtarın `{alan}`ları dillerde birebir aynı olmalı.

    Çağıran taraf tek bir argüman kümesi geçirir; İngilizce metin fazladan bir
    alan isterse KeyError, eksik bırakırsa değer sessizce kaybolur.
    """
    for anahtar in katalog["tr"]:
        assert _alanlar(katalog["tr"][anahtar]) == _alanlar(katalog["en"][anahtar]), (
            f"{ad}[{anahtar}]: format alanları dillerde farklı"
        )


@pytest.mark.parametrize("dil", ["tr", "en"])
def test_arayuz_turetilmis_anahtarlari_tam(dil):
    """`t(f"yuk.{kind}")` gibi türetilen anahtarların hepsi katalogda olmalı.

    Bunlar kod içinde dize birleştirmesiyle kurulduğu için editörde/aramada
    görünmez; core'a yeni bir yük tipi ya da mesnet tipi eklenip katalog
    unutulursa yalnız bu test yakalar.
    """
    sozluk = ui_dil.METINLER[dil]
    for kind in LOAD_TYPES:
        assert f"yuk.{kind}" in sozluk
        assert f"ipucu.{kind}" in sozluk
    for sup in SUPPORT_TYPES:
        assert f"mesnet.{sup}" in sozluk
    # Yük parametrelerinin etiketleri (app.PARAM_UNITS ile eşleşir).
    for params in (p for _, _, p in LOAD_TYPES.values()):
        for p in params:
            assert f"param.{p}" in sozluk


def test_dil_sayisal_sonucu_degistirmez():
    """`dil` yalnız mesajları etkiler; çözüm birebir aynı kalmalı."""
    model = BeamModel(
        spans=[6.0, 6.0], EI=[30_000.0] * 2,
        supports=["pin", "roller", "pin"],
        loads=[Load(1, "udl", [20.0]), Load(2, "udl", [20.0])],
    )
    r_tr, r_en = solve(model, "tr"), solve(model, "en")
    for anahtar in ("Mmax", "Mmin", "Vmax", "Vmin", "Dmax", "Dmin", "Nmax"):
        assert r_tr[anahtar] == r_en[anahtar]


def test_bilinmeyen_dil_turkceye_duser():
    """Tanımsız dil kodu hata değil, Türkçe metin üretir."""
    assert ui_dil.cevir("de", "sonuclar.baslik") == ui_dil.cevir("tr", "sonuclar.baslik")
    assert mesajlar.mesaj("a_negatif", "de") == mesajlar.mesaj("a_negatif", "tr")
    # dil=None (varsayılan) da Türkçedir — dil geçirmeyen eski çağrılar bozulmaz.
    assert mesajlar.mesaj("a_negatif") == mesajlar.mesaj("a_negatif", "tr")


def test_ceviriler_gercekten_farkli():
    """TR ve EN metinleri aynı kalmışsa çeviri unutulmuştur.

    Birim, simge ya da iki dilde ortak sözcük içeren anahtarlar haklı olarak
    aynıdır ("x [m]", "Min.", "moment"); bunlar bilerek muaf tutulur. Muafiyet
    listesine ekleme yaparken metnin gerçekten ortak olduğundan emin ol —
    liste büyüdükçe testin değeri düşer.
    """
    muaf = {"csv.x", "csv.moment", "param.M", "yuk.moment", "panel.moment",
            "gorunum.M", "kart.konum", "kart.min", "kart.min_baslik",
            "buyukluk.moment",
            # yönetmelik adları özel addır; "min." iki dilde de aynı kısaltmadır
            "yonetmelik.eurocode", "yonetmelik.ts500",
            "zarf.panel_min", "csv.moment_min"}
    ayni = [
        k for k, v in ui_dil.METINLER["tr"].items()
        if k not in muaf and v == ui_dil.METINLER["en"][k]
    ]
    assert ayni == [], f"çevrilmemiş anahtarlar: {ayni}"
