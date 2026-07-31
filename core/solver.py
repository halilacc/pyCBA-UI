"""
Çözücü: BeamModel -> PyCBA analizi -> sonuç sözlüğü.

Streamlit'e (veya başka bir arayüze) hiç bağımlı değildir; doğrudan Python'dan
çağrılabilir ve test edilebilir.
"""

import numpy as np
import pycba as cba

from .axial import solve_axial
from .mesajlar import mesaj
from .model import BeamModel


class SolverError(Exception):
    """Kullanıcıya gösterilebilir, anlaşılır çözüm hatası."""


# Açıklık başına diyagram istasyonu sayısı (`analyze(npts=...)`).
# PyCBA varsayılanı 100'dür ve ızgara EŞİT ARALIKLIDIR: yük süreksizliklerine
# (tekil yük, moment, kısmi yük uçları) istasyon EKLENMEZ (`results.py`:
# `xr = dx * np.arange(0, npts + 1)`). Tepe değer iki istasyonun arasına
# düşerse ekstrem olduğundan DÜŞÜK okunur — L=6 m'de a=2 m'deki P=100 kN için
# M_maks 133.33 yerine 132.00 çıkıyordu (%1). Hata ızgara aralığıyla orantılı
# olduğundan 100 -> 1000 onu %0.1'e indirir; ölçülen maliyet 5 açıklık + 6 yükte
# 0.9 ms -> 1.4 ms, yani pratikte bedava. Tam sıfırlanmaz: yük konumu ızgaraya
# denk gelmedikçe artık hata kalır (bkz. README "Bilinen sınırlar").
ISTASYON_SAYISI = 1000


def build_beam(model: BeamModel):
    """Analiz çalıştırmadan, şematik çizim için `pycba.Beam` nesnesi kur.

    Yüksüz/kararsız modellerde de çalışır (çizim için çözüm gerekmez);
    `beam.plot(ax=...)` ile mesnetler ve yükler şema olarak çizilir.
    Açıklık içi mafsallar `expand()` ile düğüme çevrilmiş halde kullanılır —
    şemada da bölünmüş geometri görünür (toplam uzunluk değişmez).
    """
    return cba.BeamAnalysis(**model.expand()[0].to_pycba()).beam


def _map_reactions(model: BeamModel, R_vector, Rs_vector=None) -> list:
    """PyCBA'nın kompakt tepki vektörlerini düğümlere eşle.

    `beam_results.R` yalnızca sabitlenmiş (restraint == -1) serbestlik
    derecelerinin tepkilerini DOF sırasıyla içerir. Düğüm başına iki DOF
    (düşey, dönme) olduğundan mesnet tiplerinden hangi tepkinin hangi düğüme
    ait olduğu çıkarılır.

    Yay mesnetler `R`de HİÇ GEÇMEZ: PyCBA yay kuvvetini ayrı bir vektörde
    (`beam_results.Rs`, yine DOF sırasıyla, yukarı pozitif `-k·u`) verir
    (`analysis._reactions`). İki vektör ayrı ayrı ilerletilir; yay düğümünü
    `R`den okumaya çalışmak sonraki bütün tepkileri kaydırırdı.

    Dönüş: [{"node": 1-tabanlı düğüm no, "x": konum [m],
             "V": düşey tepki [kN] | None, "M": moment tepkisi [kNm] | None}]
    """
    positions = np.concatenate([[0.0], np.cumsum(model.spans)])
    reactions = []
    it = iter(np.asarray(R_vector).ravel())
    it_s = iter(np.asarray(Rs_vector).ravel() if Rs_vector is not None else [])
    for i, sup in enumerate(model.supports):
        if sup == "spring":
            vertical, rotational = next(it_s), None
        else:
            vertical = next(it) if sup in ("pin", "roller", "fixed") else None
            rotational = next(it) if sup == "fixed" else None
        if sup != "free":
            reactions.append(
                {
                    "node": i + 1,
                    "x": float(positions[i]),
                    "V": float(vertical) if vertical is not None else None,
                    "M": float(rotational) if rotational is not None else None,
                    "H": None,  # yatay tepki; solve() eksenel çözümden doldurur
                }
            )
    return reactions


def _sehim_dizisi(vRes) -> np.ndarray:
    """Eleman sehim dizilerini, uçlardaki sıfır dolguyu onararak birleştir.

    PyCBA her elemanın dizisine ilk ve son istasyonu TEKRARLAYAN birer dolgu
    girdisi koyar (mesnetteki kesme sıçramasını taşımak için) ama sehimi yalnız
    iç ızgaraya yazar (`results.py`: `res.D[1:-1] = D`) — dolgu girdileri 0
    kalır. Mesnette sehim zaten 0 olduğu için bu normalde görünmez; çöken bir
    mesnette ya da açıklık içi mafsalın doğurduğu serbest düğümde ise sehim
    eğrisi o noktada sıfıra düşüyor gibi çizilir (PyCBA kendi çiziminde dolguyu
    `m.D[1:-1]` ile atar).

    Dolgu istasyonu gerçek uç istasyonun AYNISI olduğundan (x[0]==x[1],
    x[-1]==x[-2]) komşu değerin kopyalanması yaklaşıklık değil, tam düzeltmedir;
    dizi boyu korunur, böylece M/V ile aynı `x` ızgarası kullanılmaya devam eder.
    """
    parcalar = []
    for mr in vRes:
        d = np.asarray(mr.D, dtype=float).copy()
        d[0], d[-1] = d[1], d[-2]
        parcalar.append(d)
    return np.concatenate(parcalar)


def solve(model: BeamModel, dil: str = None) -> dict:
    """Modeli çöz ve sonuçları düz bir sözlük olarak döndür.

    `dil` yalnız SolverError mesajlarının dilini belirler (bkz. core/mesajlar.py);
    sayısal sonuçları etkilemez. Verilmezse mesajlar Türkçedir.

    Dönen anahtarlar:
        x, M, V, D   : diyagram dizileri (np.ndarray; D = sehim [m])
        xN, N        : normal kuvvet diyagramı (kendi apsis dizisiyle; çekme +)
        ea_uyari     : True ise yatay tepkiler EA=1 varsayımına bağlı
                       (bkz. core/axial.py); sunum katmanı uyarı gösterir
        reactions    : mesnet tepkileri (düğüm bazında; bkz. _map_reactions;
                       "H" yatay tepki, eksenel çözümden gelir)
        Mmax, Mmin   : ekstrem momentler [kNm]
        Vmax, Vmin   : ekstrem kesme kuvvetleri [kN]
        Nmax, Nmin   : ekstrem normal kuvvetler [kN]
        Dmax, Dmin   : ekstrem sehimler [m]
        analysis     : PyCBA BeamAnalysis nesnesi (çizim için)

    Kararsız/çözülemez sistemde SolverError fırlatır.
    """
    # Doğrulama ÖNCE gelir: geçersiz bir mafsal düğümü ya da açıklığı aşan bir
    # konum, expand() içinde ham (SolverError'a sarılmamış, anlaşılmaz) bir
    # ValueError'a ya da yanıltıcı bir "mekanizma" mesajına dönüşür. app.py
    # zaten validate() çağırıyor; bu satır core'un tek başına da doğru
    # davranmasını sağlar.
    errors = model.validate(dil)
    if errors:
        raise SolverError(" / ".join(errors))

    # Mekanizma ön-kontrolü: mafsal eklendikçe sistem kolayca hipostatik olur ve
    # PyCBA'dan gelen kararsızlık hatası kullanıcıya nedeni anlatmaz. Derece
    # sayımı (bkz. BeamModel.static_degree) mekanizmayı isabetli bir mesajla
    # yakalar; yetersiz kaldığı düzenleri aşağıdaki is_stable() yine tutar.
    # Açıklık içi mafsallar burada düğüme çevrilir; bu noktadan sonra `gm`
    # (genişletilmiş model) kullanılır. node_map, tepkileri kullanıcının düğüm
    # numaralandırmasına geri çevirmek içindir.
    gm, node_map = model.expand()
    derece = model.static_degree()
    if derece < 0:
        raise SolverError(mesaj(
            "mekanizma", dil, derece=derece,
            n_mafsal=len(model.hinges) + len(model.span_hinges),
        ))
    try:
        ba = cba.BeamAnalysis(**gm.to_pycba(dil))
        # PyCBA'nın kararsızlık denetimi analyze() içinde ValueError fırlatır ve
        # metni İngilizcedir, üstelik kullanıcıya `analyze(check_stability=False)`
        # gibi bir API önerir. is_stable() aynı denetimi önden yapar, biz de kendi
        # mesajımızı veririz. (True sonucu önbelleklenir; analyze tekrar bakmaz.)
        # np.linalg.LinAlgError ayrı bir dalda YAKALANMAZ: numpy'da ValueError'ın
        # alt sınıfıdır, aşağıdaki dal onu zaten tutar.
        if not ba.is_stable():
            raise SolverError(mesaj("tekil_matris", dil))
        ba.analyze(npts=ISTASYON_SAYISI)
    except ValueError as e:
        raise SolverError(mesaj("cozulemedi", dil, hata=e)) from e

    res = ba.beam_results.results
    M, V, x = (np.asarray(a) for a in (res.M, res.V, res.x))
    D = _sehim_dizisi(ba.beam_results.vRes)
    if not (np.all(np.isfinite(M)) and np.all(np.isfinite(V)) and np.all(np.isfinite(D))):
        raise SolverError(mesaj("sonuc_tanimsiz", dil))

    # Eksenel çözüm (PyCBA'dan bağımsız). Yatay tutulu mesnet yoksa ve eksenel
    # yük varsa kullanıcıya gösterilebilir hata üret.
    try:
        ax_res = solve_axial(gm, dil)
    except ValueError as e:
        raise SolverError(mesaj("eksenel_cozulemedi", dil, hata=e)) from e

    reactions = _map_reactions(gm, ba.beam_results.R, ba.beam_results.Rs)
    for r in reactions:
        if r["node"] in ax_res["H"]:
            r["H"] = ax_res["H"][r["node"]]
        # "node" kullanıcının düğüm numarasına döner; çizim katmanı genişletilmiş
        # indeksi ("node_expanded") kullanır. Açıklık içi mafsal yoksa ikisi aynıdır.
        r["node_expanded"] = r["node"]
        r["node"] = node_map[r["node"] - 1]
    N = ax_res["N"]

    return {
        "x": x,
        "M": M,
        "V": V,
        "D": D,
        "xN": ax_res["xN"],
        "N": N,
        "ea_uyari": ax_res["ea_uyari"],
        "reactions": reactions,
        "Nmax": float(N.max()),
        "Nmin": float(N.min()),
        "Mmax": float(M.max()),
        "Mmin": float(M.min()),
        "Vmax": float(V.max()),
        "Vmin": float(V.min()),
        "Dmax": float(D.max()),
        "Dmin": float(D.min()),
        "analysis": ba,
    }
