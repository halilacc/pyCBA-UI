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


def build_beam(model: BeamModel):
    """Analiz çalıştırmadan, şematik çizim için `pycba.Beam` nesnesi kur.

    Yüksüz/kararsız modellerde de çalışır (çizim için çözüm gerekmez);
    `beam.plot(ax=...)` ile mesnetler ve yükler şema olarak çizilir.
    Açıklık içi mafsallar `expand()` ile düğüme çevrilmiş halde kullanılır —
    şemada da bölünmüş geometri görünür (toplam uzunluk değişmez).
    """
    return cba.BeamAnalysis(**model.expand()[0].to_pycba()).beam


def _map_reactions(model: BeamModel, R_vector) -> list:
    """PyCBA'nın kompakt tepki vektörünü düğümlere eşle.

    `beam_results.R` yalnızca sabitlenmiş (restraint == -1) serbestlik
    derecelerinin tepkilerini DOF sırasıyla içerir. Düğüm başına iki DOF
    (düşey, dönme) olduğundan mesnet tiplerinden hangi tepkinin hangi düğüme
    ait olduğu çıkarılır.

    Dönüş: [{"node": 1-tabanlı düğüm no, "x": konum [m],
             "V": düşey tepki [kN] | None, "M": moment tepkisi [kNm] | None}]
    """
    positions = np.concatenate([[0.0], np.cumsum(model.spans)])
    reactions = []
    it = iter(np.asarray(R_vector).ravel())
    for i, sup in enumerate(model.supports):
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
        ba.analyze()
    except ValueError as e:
        raise SolverError(mesaj("cozulemedi", dil, hata=e)) from e

    res = ba.beam_results.results
    M, V, D, x = (np.asarray(a) for a in (res.M, res.V, res.D, res.x))
    if not (np.all(np.isfinite(M)) and np.all(np.isfinite(V)) and np.all(np.isfinite(D))):
        raise SolverError(mesaj("sonuc_tanimsiz", dil))

    # Eksenel çözüm (PyCBA'dan bağımsız). Yatay tutulu mesnet yoksa ve eksenel
    # yük varsa kullanıcıya gösterilebilir hata üret.
    try:
        ax_res = solve_axial(gm, dil)
    except ValueError as e:
        raise SolverError(mesaj("eksenel_cozulemedi", dil, hata=e)) from e

    reactions = _map_reactions(gm, ba.beam_results.R)
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
