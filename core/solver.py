"""
Çözücü: BeamModel -> PyCBA analizi -> sonuç sözlüğü.

Streamlit'e (veya başka bir arayüze) hiç bağımlı değildir; doğrudan Python'dan
çağrılabilir ve test edilebilir.
"""

import numpy as np
import pycba as cba

from .axial import solve_axial
from .model import BeamModel


class SolverError(Exception):
    """Kullanıcıya gösterilebilir, anlaşılır çözüm hatası."""


def build_beam(model: BeamModel):
    """Analiz çalıştırmadan, şematik çizim için `pycba.Beam` nesnesi kur.

    Yüksüz/kararsız modellerde de çalışır (çizim için çözüm gerekmez);
    `beam.plot(ax=...)` ile mesnetler ve yükler şema olarak çizilir.
    """
    return cba.BeamAnalysis(**model.to_pycba()).beam


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


def solve(model: BeamModel) -> dict:
    """Modeli çöz ve sonuçları düz bir sözlük olarak döndür.

    Dönen anahtarlar:
        x, M, V, D   : diyagram dizileri (np.ndarray; D = sehim [m])
        xN, N        : normal kuvvet diyagramı (kendi apsis dizisiyle; çekme +)
        reactions    : mesnet tepkileri (düğüm bazında; bkz. _map_reactions;
                       "H" yatay tepki, eksenel çözümden gelir)
        Mmax, Mmin   : ekstrem momentler [kNm]
        Vmax, Vmin   : ekstrem kesme kuvvetleri [kN]
        Nmax, Nmin   : ekstrem normal kuvvetler [kN]
        Dmax, Dmin   : ekstrem sehimler [m]
        analysis     : PyCBA BeamAnalysis nesnesi (çizim için)

    Kararsız/çözülemez sistemde SolverError fırlatır.
    """
    try:
        ba = cba.BeamAnalysis(**model.to_pycba())
        ba.analyze()
    except ValueError as e:
        raise SolverError(
            f"Sistem çözülemedi: {e}\n"
            "Mesnetleri kontrol edin — kiriş kararsız (mekanizma) olabilir "
            "(örn. tek bir mafsallı mesnet yeterli değildir)."
        ) from e
    except np.linalg.LinAlgError as e:
        raise SolverError(
            "Sistem kararsız: rijitlik matrisi tekil. Mesnetleri kontrol edin."
        ) from e

    res = ba.beam_results.results
    M, V, D, x = (np.asarray(a) for a in (res.M, res.V, res.D, res.x))
    if not (np.all(np.isfinite(M)) and np.all(np.isfinite(V)) and np.all(np.isfinite(D))):
        raise SolverError(
            "Sistem kararsız: sonuçlar sonsuz/tanımsız çıktı. Mesnetleri kontrol edin."
        )

    # Eksenel çözüm (PyCBA'dan bağımsız). Yatay tutulu mesnet yoksa ve eksenel
    # yük varsa kullanıcıya gösterilebilir hata üret.
    try:
        ax_res = solve_axial(model)
    except ValueError as e:
        raise SolverError(f"Eksenel sistem çözülemedi: {e}") from e

    reactions = _map_reactions(model, ba.beam_results.R)
    for r in reactions:
        if r["node"] in ax_res["H"]:
            r["H"] = ax_res["H"][r["node"]]
    N = ax_res["N"]

    return {
        "x": x,
        "M": M,
        "V": V,
        "D": D,
        "xN": ax_res["xN"],
        "N": N,
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
