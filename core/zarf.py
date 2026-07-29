"""Yük düzenleri ve zarf diyagramları.

Hareketli yük (Q) her açıklıkta aynı anda durmak zorunda değildir ve **hiçbir tek
yükleme her kesitte yönetici olmaz**: açıklık momentini o açıklık tek başına
yüklüyken, mesnet momentini komşu iki açıklık birlikte yüklüyken en büyük yapar.
Bu modül standart düzenleri kurar, her birini `solver.solve` ile çözer ve
noktasal maksimum/minimum alarak zarfı üretir.

PyCBA'nın kendi `LoadPattern`/`Envelopes` sınıfları BİLEREK kullanılmıyor:

- Sehim zarfı elde ediliyor (PyCBA zarfı yalnız M, V ve tepki taşır).
- Tepki zarfı doğrudan kullanıcının düğüm numarasıyla çıkıyor.
- PyCBA patternlemeyi GENİŞLETİLMİŞ açıklıklara uygular; açıklık içi mafsallı
  2 açıklıklı bir kirişte 3 açıklık görüp kullanıcının numaralandırmasıyla
  örtüşmeyen 5 düzen üretir. Burada düzenler KULLANICI açıklıkları üzerinde
  kurulur, genişletme her düzenin içinde `solve()` tarafından yapılır.

Sonuçlar PyCBA ile birebir aynıdır (bkz. tests/test_core.py çapraz doğrulaması).
Arayüzden bağımsızdır; dil yalnız hata mesajları için parametre olarak geçer.
"""

from dataclasses import dataclass, replace
from typing import List, Optional, Tuple

import numpy as np

from .model import BeamModel
from .solver import solve

# Yönetmelik -> (γ_G,maks, γ_G,min, γ_Q,maks, γ_Q,min)
# Bir düzende YÜKLÜ açıklıklar (γ_G,maks, γ_Q,maks), diğerleri (γ_G,min, γ_Q,min)
# ile alınır: hareketli yük yüklenmeyen açıklıktan kalkar (γ_Q,min = 0), sabit
# yük de orada ELVERİŞLİ olduğu için azaltılır. Mesnet kalkmasını ve moment
# işaret değiştirmesini yakalayan budur. (PyCBA `pattern.py:142-147` ile aynı
# kural; çapraz doğrulaması tests/test_core.py'de.)
KATSAYI_SETLERI = {
    "eurocode": (1.35, 1.00, 1.50, 0.00),  # EN 1990, 6.10 (STR)
    "ts500": (1.40, 0.90, 1.60, 0.00),     # TS 500, 6.2.6
}
VARSAYILAN_SET = "eurocode"


@dataclass(frozen=True)
class Duzen:
    """Tek bir yükleme düzeni (kombinasyon).

    anahtar : "tum" | "tek" | "cift" | "mesnet" — sunum katmanı adı buradan
              çevirir (bkz. ui_dil.py `duzen.*`); çekirdek dilsizdir.
    spans   : MAKSİMUM katsayılarla yüklenen açıklıklar (1-tabanlı, kullanıcı
              numaralandırması). Listede olmayan açıklıklar minimum
              katsayılarla alınır.
    dugum   : "mesnet" düzeninde negatif momenti aranan mesnet düğümü; diğer
              düzenlerde None.
    """

    anahtar: str
    spans: Tuple[int, ...]
    dugum: Optional[int] = None


def duzenler(n_span: int) -> List[Duzen]:
    """Standart yük düzenlerini üret (maksimum katsayıyla yüklenen açıklıklar).

    - "tum"    : bütün açıklıklar yüklü (kalıcı durum, mesnet momentlerinin çoğu)
    - "tek"    : 1, 3, 5, ... açıklıklar — tek numaralı açıklıkların momenti
    - "cift"   : 2, 4, 6, ... açıklıklar
    - "mesnet" : her ara mesnedin İKİ komşu açıklığı — o mesnetteki negatif
                 momentin maksimumu

    Aynı açıklık kümesini veren düzenler tekilleştirilir (2 açıklıkta "tüm" ile
    "2. mesnedin komşuları" aynı şeydir); ilk sıradaki ad korunur, bu yüzden
    liste en anlamlı addan başlar.
    """
    ham = [("tum", tuple(range(1, n_span + 1)), None)]
    if n_span > 1:
        ham.append(("tek", tuple(range(1, n_span + 1, 2)), None))
        ham.append(("cift", tuple(range(2, n_span + 1, 2)), None))
        for dugum in range(2, n_span + 1):  # ara mesnetler: düğüm 2..n_span
            ham.append(("mesnet", (dugum - 1, dugum), dugum))

    out, gorulen = [], set()
    for anahtar, spans, dugum in ham:
        if not spans or spans in gorulen:
            continue
        gorulen.add(spans)
        out.append(Duzen(anahtar, spans, dugum))
    return out


def kombinasyonlar(model: BeamModel, katsayilar) -> List[Duzen]:
    """Çözülecek düzenlerin listesi.

    Normalde `duzenler()`in tamamıdır. Maksimum ve minimum katsayılar modeldeki
    yükler için ayırt edilemiyorsa (γ_G,maks = γ_G,min ve hareketli yük yok ya
    da γ_Q,maks = γ_Q,min) bütün düzenler aynı sonucu verir; o durumda tek
    düzenle yetinilir — hem gereksiz çözüm yapılmaz hem "yöneten düzen"
    bilgisi rastgele bir addan seçilmiş olmaz.
    """
    g_maks, g_min, q_maks, q_min = katsayilar
    ayni_G = abs(g_maks - g_min) < 1e-12
    ayni_Q = (not any(ld.sinif == "Q" for ld in model.loads)
              or abs(q_maks - q_min) < 1e-12)
    if ayni_G and ayni_Q:
        return [Duzen("tum", tuple(range(1, model.n_spans + 1)))]
    return duzenler(model.n_spans)


def olcekli_model(model: BeamModel, duzen: Duzen, katsayilar) -> BeamModel:
    """Bir düzen için yükleri katsayılarla ölçeklenmiş model kopyası döndür.

    Düzenin YÜKLÜ açıklıklarında (γ_G,maks, γ_Q,maks), diğerlerinde
    (γ_G,min, γ_Q,min) uygulanır.

    Yük SATIRLARI silinmez, yalnız şiddetleri çarpılır (γ_Q,min = 0 ise yük
    sıfırlanır). Böylece her düzende PyCBA'ya aynı yapıda bir yük matrisi gider
    ve istasyon ızgarası birebir aynı kalır — zarfı noktasal karşılaştırmak
    ancak böyle mümkündür.

    Mesnet çökmeleri KALICI etkidir: patternlenmez, katsayı da uygulanmaz.
    """
    g_maks, g_min, q_maks, q_min = katsayilar
    yeni_loads = []
    for ld in model.loads:
        yuklu = ld.span in duzen.spans
        if ld.sinif == "Q":
            k = q_maks if yuklu else q_min
        else:
            k = g_maks if yuklu else g_min
        yeni_loads.append(ld.scaled(k))
    return replace(model, loads=yeni_loads)


def _zarf(yigin: np.ndarray):
    """(n_düzen, n_istasyon) yığınından zarfı ve yöneten düzen indislerini çıkar.

    Zarf dizileri SIFIRDAN başlatılır (`Mmax >= 0`, `Mmin <= 0`): PyCBA'nın
    çizim geleneği budur (`results.py:468` zarfı sıfır dizisiyle başlatıp
    üzerine yazar), zarf ekseni sarar. Yani tüm düzenlerde negatif olan bir
    kesitte `Mmax` 0 çıkar — bu bir hata değil, bilinçli konvansiyondur; asıl
    değer diğer taraftaki zarfta zaten görünür.

    Dönüş: (maks, min, argmaks, argmin, ham_maks, ham_min)
    """
    ham_maks, ham_min = yigin.max(axis=0), yigin.min(axis=0)
    return (np.maximum(ham_maks, 0.0), np.minimum(ham_min, 0.0),
            yigin.argmax(axis=0), yigin.argmin(axis=0), ham_maks, ham_min)


def solve_envelope(model: BeamModel, katsayilar=None, dil: str = None) -> dict:
    """Yük düzenlerini çöz ve zarf sonuçlarını döndür.

    katsayilar : (γ_G,maks, γ_G,min, γ_Q,maks, γ_Q,min); verilmezse
                 KATSAYI_SETLERI[VARSAYILAN_SET].
    dil        : yalnız hata mesajlarının dili (bkz. core/mesajlar.py).

    Dönen anahtarlar:
        x                      : ortak apsis dizisi [m]
        Mmax/Mmin, Vmax/Vmin,
        Dmax/Dmin              : zarf dizileri (sıfıra kenetli; D metre)
        ekstrem                : {"Mmax": {...}, "Mmin", "Vmax", "Vmin",
                                  "Dmax", "Dmin"} — her biri
                                 {"deger", "x", "duzen", "esdeger"}; "duzen"
                                 yöneten Duzen (kenetlenmiş sıfırda None),
                                 "esdeger" o düzende aynı kesitteki M/V/D
        reactions              : [{"node", "x", "Vmax", "Vmin", "Vmax_duzen",
                                   "Vmin_duzen", "Mmax", "Mmin", "Hmax",
                                   "Hmin"}] — tepkiler KENETLENMEZ (sıfıra
                                  çekilseydi hep kalkan bir mesnet 0 görünürdü)
        kombinasyonlar         : çözülen Duzen listesi
        hareketli_var          : modelde Q sınıfı yük var mı (yoksa zarf tek
                                 düzene iner; sunum katmanı bunu söyler)
        ea_uyari               : herhangi bir düzende EA uyarısı doğdu mu

    Kararsız/geçersiz modelde `solver.SolverError` fırlatır (solve ile aynı).
    """
    if katsayilar is None:
        katsayilar = KATSAYI_SETLERI[VARSAYILAN_SET]
    katsayilar = tuple(float(k) for k in katsayilar)

    komb = kombinasyonlar(model, katsayilar)
    sonuclar = [solve(olcekli_model(model, d, katsayilar), dil) for d in komb]

    x = sonuclar[0]["x"]
    if any(len(r["x"]) != len(x) or not np.allclose(r["x"], x) for r in sonuclar):
        # Geometri düzenden düzene değişmediği için ızgara da değişemez; burası
        # tutmuyorsa ölçekleme yük satırlarının SAYISINI değiştirmiş demektir.
        raise RuntimeError("Zarf: düzenlerin istasyon ızgaraları örtüşmüyor.")

    yiginlar = {ad: np.vstack([r[ad] for r in sonuclar]) for ad in ("M", "V", "D")}
    cikti = {"x": x}
    ekstrem = {}
    for ad, yigin in yiginlar.items():
        maks, minm, i_maks, i_min, ham_maks, ham_min = _zarf(yigin)
        cikti[f"{ad}max"], cikti[f"{ad}min"] = maks, minm
        for uc, zarf_dizi, idx_dizi, ham in (
            ("max", maks, i_maks, ham_maks), ("min", minm, i_min, ham_min),
        ):
            # Konum HAM zarftan okunur, değer kenetlenmiş zarftan: her kesitte
            # kenetlenmiş bir diyagramda (ör. konsolun momenti) argmax düz sıfır
            # dizisinin ilk elemanına düşer ve rastgele bir x bildirirdi; ham
            # dizide "sıfıra en yakın" kesit anlamlıdır. Kenetleme olmayan
            # olağan durumda iki indis zaten aynıdır.
            i = int(ham.argmax() if uc == "max" else ham.argmin())
            kenetli = abs(zarf_dizi[i] - ham[i]) > 1e-12  # sıfıra çekilmiş mi
            j = int(idx_dizi[i])
            ekstrem[f"{ad}{uc}"] = {
                "deger": float(zarf_dizi[i]),
                "x": float(x[i]),
                "duzen": None if kenetli else komb[j],
                "esdeger": None if kenetli else {
                    b: float(yiginlar[b][j, i]) for b in ("M", "V", "D")
                },
            }
    cikti["ekstrem"] = ekstrem

    # --- tepki zarfı -------------------------------------------------------
    # Düğüm sırası her düzende aynıdır (geometri sabit), yine de düğüm no ile
    # eşleştirilir — sıraya güvenmek sessiz bir kaymayı gizlerdi.
    tepkiler = []
    for k, r0 in enumerate(sonuclar[0]["reactions"]):
        satir = {"node": r0["node"], "x": r0["x"]}
        for alan in ("V", "M", "H"):
            degerler = []
            for r in sonuclar:
                rr = r["reactions"][k]
                if rr["node"] != r0["node"]:
                    raise RuntimeError("Zarf: tepki düğüm sırası düzenler arasında değişti.")
                degerler.append(rr[alan])
            if all(d is None for d in degerler):  # ör. mafsallı mesnette M
                satir[f"{alan}max"] = satir[f"{alan}min"] = None
                continue
            dizi = np.array([0.0 if d is None else float(d) for d in degerler])
            satir[f"{alan}max"] = float(dizi.max())
            satir[f"{alan}min"] = float(dizi.min())
            if alan == "V":
                satir["Vmax_duzen"] = komb[int(dizi.argmax())]
                satir["Vmin_duzen"] = komb[int(dizi.argmin())]
        tepkiler.append(satir)
    cikti["reactions"] = tepkiler

    cikti["kombinasyonlar"] = komb
    cikti["hareketli_var"] = any(ld.sinif == "Q" for ld in model.loads)
    cikti["ea_uyari"] = any(r["ea_uyari"] for r in sonuclar)
    return cikti
