"""
Eksenel (normal kuvvet) çözücü — PyCBA'dan bağımsız.

PyCBA yalnızca düşey yükleri çözer; eksenel yükler burada tek boyutlu çubuk
sonlu eleman modeliyle çözülür. EA sabit (=1) alınır: izostatik durumda
(tek yatay tutulu mesnet) sonuç EA'dan bağımsız ve kesindir; hiperstatik
durumda (birden çok pin/fixed) açıklıklar arası EA oranı eşit varsayılır.

İşaret kabulü:
    - Yük değeri +x (sağa) yönünde pozitif.
    - İç normal kuvvet N çekmede pozitif.
    - Yatay mesnet tepkisi +x yönünde pozitif.

Yatay tutulu mesnet tipleri: pin ve fixed (roller/free yatayda serbest).
"""

import numpy as np

from .mesajlar import mesaj
from .model import BeamModel, AXIAL_KINDS

# Yatayda tutulu mesnet tipleri
HORIZ_RESTRAINED = ("pin", "fixed")

_TOL = 1e-9


def solve_axial(model: BeamModel, dil: str = None) -> dict:
    """Modelin eksenel yüklerini çöz.

    Dönüş sözlüğü:
        xN : diyagram apsisleri [m] (eleman uçları; süreksizlikler çift nokta)
        N  : normal kuvvet dizisi [kN] (çekme +)
        H  : {1-tabanlı düğüm no: yatay tepki [kN]} — yalnız yatay tutulu düğümler

    Eksenel yük varken hiçbir yatay tutulu mesnet yoksa ValueError fırlatır
    (çözücü katmanı bunu SolverError'a çevirir).
    """
    node_x = np.concatenate([[0.0], np.cumsum(model.spans)])
    total_L = float(node_x[-1])
    restrained = [i for i, s in enumerate(model.supports) if s in HORIZ_RESTRAINED]

    axial = [ld for ld in model.loads if ld.kind in AXIAL_KINDS]
    if not axial:
        return {
            "xN": np.array([0.0, total_L]),
            "N": np.zeros(2),
            "H": {i + 1: 0.0 for i in restrained},
        }
    if not restrained:
        raise ValueError(mesaj("eksenel_mesnet_yok", dil))

    # Kırılma noktaları: mesnet düğümleri + tekil eksenel yük konumları.
    # (Eksenel UDL tüm açıklığa yayılır; uçları zaten düğüm noktalarıdır.)
    points = []   # (x, P) tekil eksenel yükler
    udls = []     # (x1, x2, n) açıklık boyu yayılı eksenel yükler
    breakpoints = set(np.round(node_x, 9))
    for ld in axial:
        x0 = float(node_x[ld.span - 1])
        if ld.kind == "axial_point":
            N_val, a = ld.values
            xp = round(x0 + float(a), 9)
            points.append((xp, float(N_val)))
            breakpoints.add(xp)
        else:  # axial_udl
            udls.append((x0, float(node_x[ld.span]), float(ld.values[0])))

    xs = np.array(sorted(breakpoints))
    n_node = len(xs)
    n_el = n_node - 1

    # Rijitlik matrisi ve yük vektörü (EA = 1)
    K = np.zeros((n_node, n_node))
    F = np.zeros(n_node)
    w_el = np.zeros(n_el)  # elemandaki toplam yayılı eksenel yük [kN/m]
    for e in range(n_el):
        xa, xb = xs[e], xs[e + 1]
        Le = xb - xa
        k = 1.0 / Le
        K[e, e] += k
        K[e + 1, e + 1] += k
        K[e, e + 1] -= k
        K[e + 1, e] -= k
        for x1, x2, w in udls:
            if x1 - _TOL <= xa and xb <= x2 + _TOL:
                w_el[e] += w
        F[e] += w_el[e] * Le / 2.0
        F[e + 1] += w_el[e] * Le / 2.0
    for xp, P in points:
        F[int(np.argmin(np.abs(xs - xp)))] += P

    # Sınır koşulları: yatay tutulu mesnet düğümlerinde u = 0
    fixed_idx = [int(np.argmin(np.abs(xs - node_x[i]))) for i in restrained]
    free = [i for i in range(n_node) if i not in fixed_idx]
    u = np.zeros(n_node)
    if free:
        u[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])

    # Yatay tepkiler: R = K·u − F (tutulu DOF'larda)
    R_full = K @ u - F
    H = {
        node + 1: float(R_full[idx])
        for node, idx in zip(restrained, fixed_idx)
    }

    # Diyagram: her elemanda N lineerdir; uç değerler yeterli.
    # N(s) = (u_b − u_a)/Le + w·(Le/2 − s), s: eleman içi yerel konum.
    xN, N = [], []
    for e in range(n_el):
        Le = xs[e + 1] - xs[e]
        C = (u[e + 1] - u[e]) / Le + w_el[e] * Le / 2.0
        xN.extend([xs[e], xs[e + 1]])
        N.extend([C, C - w_el[e] * Le])
    return {"xN": np.asarray(xN, dtype=float), "N": np.asarray(N, dtype=float), "H": H}
