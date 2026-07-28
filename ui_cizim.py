"""
Şema çizim yardımcıları — sunum katmanı (Streamlit'e bağımlı DEĞİL).

PyCBA'nın çizicisi yalnız düşey yükleri ve düşey/moment tepkilerini tanır;
eksenel yükler ve yatay tepkiler burada matplotlib ile şemaya eklenir.
Hesap `core/`dedir; bu modül yalnızca çizer. `app.py` kullanır, ancak
Streamlit gerektirmediği için tarayıcısız da test edilebilir.
"""

import numpy as np
from matplotlib.lines import Line2D
from pycba.render import BeamPlotter, Support

from core import AXIAL_KINDS, build_beam
from ui_dil import cevir

# Şema renk paleti (tek kaynak). "Yeşil = normal kuvvet" görsel dili şema ile
# app.py'deki Plotly normal kuvvet diyagramında ortaktır; app.py bu yeşili
# buradan alır ki iki katman ayrışmasın. NORMAL_KUVVET_YESILI, matplotlib
# tab:green ile birebir aynı hex'tir (#2ca02c).
EKSENEL_YUK_MAVISI = "tab:blue"      # uygulanan eksenel yük oku
NORMAL_KUVVET_YESILI = "#2ca02c"     # yatay tepki oku + N diyagramı

# Eksenel yük alt-tip anahtarları core.LOAD_TYPES ile aynı olmalı; anahtar
# adı değişirse çizim sessizce bozulmasın diye import anında doğrulanır.
_AXIAL_POINT, _AXIAL_UDL = "axial_point", "axial_udl"
assert {_AXIAL_POINT, _AXIAL_UDL} <= AXIAL_KINDS, (
    "Eksenel yük anahtarları core.AXIAL_KINDS ile uyumsuz — ui_cizim güncellenmeli."
)


def ciz_sema(ax, model, reactions=None, dil=None):
    """Kiriş şemasını modeldeki GERÇEK mesnet tipleriyle çiz.

    PyCBA'nın BeamPlotter'ı mesnet türünü tutulu DOF vektöründen tahmin eder;
    PyCBA'da yatay DOF olmadığından pin ile roller aynı görünür ve çizici
    "ilk düşey mesnet pin, kalanlar roller" kuralını uygular — kullanıcının
    mesnet seçimi şemaya yansımaz. Burada glif listesi (bp.supports) çizimden
    önce modeldeki mesnet tipleriyle yeniden kurulur; tip adları ("pin",
    "roller", "fixed") PyCBA'nın glif sabitleriyle birebir aynıdır, "free"
    çizilmez.

    reactions verilirse (core.solve çıktısı) düşey/moment tepki okları ve
    yatay tepkiler de eklenir; eksenel yükler her durumda çizilir.
    """
    # Açıklık içi mafsallar düğüme çevrilmiş halde çizilir (bkz. BeamModel.expand):
    # şemada bölünmüş açıklıklar ve mesnetsiz mafsal düğümü görünür. Toplam
    # uzunluk ve yük konumları değişmez.
    model = model.expand()[0]
    bp = BeamPlotter(build_beam(model), loads=None)  # loads=None -> beam.LM
    node_x = np.concatenate([[0.0], np.cumsum(model.spans)])
    n_node = len(node_x)
    # `Support.node` PyCBA'da YALNIZCA mesnet harfini üretmek için kullanılır
    # (render.py: chr(ord("A") + s.node)); glif konumu x'ten gelir, tepki okları
    # ise ayrı bir sözlükle çizilir. Düğüm indeksini olduğu gibi verirsek çizilmeyen
    # düğümler (free — özellikle açıklık içi mafsalın doğurduğu ara düğüm) harf
    # atlatır: kullanıcı 3 mesnet görürken etiketler A, B, D olur. Bu yüzden harfler
    # ÇİZİLEN mesnetler üzerinde sıfırdan sırayla numaralanır.
    bp.supports = [
        Support(x=float(node_x[i]), kind=sup, node=sira,
                at_left_end=(i == 0), at_right_end=(i == n_node - 1))
        for sira, (i, sup) in enumerate(
            (i, s) for i, s in enumerate(model.supports) if s != "free"
        )
    ]
    bp.render_mpl(ax=ax, dimensions=True, load_values=True)
    if reactions:
        # BeamPlotter 0-tabanlı ve GENİŞLETİLMİŞ düğüm dizisiyle çalışır; bu
        # yüzden "node" (kullanıcı numarası) değil "node_expanded" kullanılır.
        # Sıfır tepkiler atlanır.
        def _i(r):
            return r.get("node_expanded", r["node"]) - 1
        vert = {_i(r): r["V"] for r in reactions
                if r["V"] is not None and abs(r["V"]) > 1e-6}
        mom = {_i(r): r["M"] for r in reactions
               if r["M"] is not None and abs(r["M"]) > 1e-6}
        bp.render_reactions_mpl(ax, vert, mom)
        ciz_yatay_tepkiler(ax, model, reactions)
    # Mafsal dairesi AYRICA ÇİZİLMEZ: PyCBA'nın çizicisi iç mafsalları eletype'tan
    # kendisi çıkarıp (render.py `_infer_hinges`) beyaz daire olarak çiziyor.
    # Burada ikinci bir daire çizmek aynı glifi üst üste bindiriyordu.
    ciz_eksenel_yukler(ax, model)
    _ciz_legend(ax, model, reactions, dil)


def _ciz_legend(ax, model, reactions, dil=None):
    """Şemadaki renk kodlarını açıklayan legend ekle (yalnız çizilen kategoriler).

    Renk dili: kırmızı = düşey yük, mavi = eksenel yük, yeşil = mesnet tepkisi
    (düşey/moment/yatay). PyCBA `render_mpl` yükleri tab:red, `render_reactions_mpl`
    tepkileri tab:green çizer; eksenel yük mavi + yatay tepki yeşil bu modülde
    eklenir. Proxy handle'lar boş veriyle kurulur (eksen sınırlarını bozmaz).
    """
    girisler = []
    if any(ld.kind not in AXIAL_KINDS for ld in model.loads):
        girisler.append(("tab:red", cevir(dil, "sema.legend.dusey")))
    if any(ld.kind in AXIAL_KINDS for ld in model.loads):
        girisler.append((EKSENEL_YUK_MAVISI, cevir(dil, "sema.legend.eksenel")))
    tepki_var = bool(reactions) and any(
        (r.get("V") and abs(r["V"]) > 1e-6)
        or (r.get("M") and abs(r["M"]) > 1e-6)
        or (r.get("H") and abs(r["H"]) > 1e-6)
        for r in reactions
    )
    if tepki_var:
        girisler.append((NORMAL_KUVVET_YESILI, cevir(dil, "sema.legend.tepki")))
    if not girisler:
        return
    handles = [
        Line2D([], [], color=c, lw=2.2, marker=">", markersize=7, label=ad)
        for c, ad in girisler
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=8, framealpha=0.9)


def ciz_eksenel_yukler(ax, model):
    """Eksenel yükleri şemaya mavi yatay ok olarak ekle (+ değer sağa).

    Ok kiriş ekseninin hemen üstünde, kuvvet yönünü gösterir; düşey yüklerin
    kırmızısından ayırt edilsin diye mavi kullanılır.
    """
    node_x = np.concatenate([[0.0], np.cumsum(model.spans)])
    total_L = float(node_x[-1])
    y0, y1 = ax.get_ylim()
    dy = y1 - y0
    alen = 0.05 * total_L  # ok uzunluğu [m]
    y = 0.04 * dy          # kiriş ekseninin hemen üstü
    ok_stili = dict(arrowstyle="-|>", color=EKSENEL_YUK_MAVISI, lw=2, mutation_scale=16)
    for ld in model.loads:
        if ld.kind == _AXIAL_POINT:
            N_val, a = ld.values
            x = float(node_x[ld.span - 1]) + float(a)
            sgn = 1 if N_val >= 0 else -1
            # Ok ucu uygulama noktasında, kuvvet yönünü gösterir; etiket mutlak
            # değerdir (yönü ok verir — "-10 kN" + sola ok çifte olumsuz okunur).
            ax.annotate("", xy=(x, y), xytext=(x - sgn * alen, y), arrowprops=ok_stili)
            ax.text(x - sgn * alen / 2, y + 0.07 * dy, f"{abs(N_val):g} kN",
                    color=EKSENEL_YUK_MAVISI, ha="center", fontsize=9)
        elif ld.kind == _AXIAL_UDL:
            n_val = float(ld.values[0])
            xa, xb = float(node_x[ld.span - 1]), float(node_x[ld.span])
            sgn = 1 if n_val >= 0 else -1
            yarim = 0.45 * alen
            for xq in np.linspace(xa + 0.12 * (xb - xa), xb - 0.12 * (xb - xa), 4):
                ax.annotate("", xy=(xq + sgn * yarim, y), xytext=(xq - sgn * yarim, y),
                            arrowprops=dict(ok_stili, lw=1.5, mutation_scale=12))
            ax.text((xa + xb) / 2, y + 0.07 * dy, f"{abs(n_val):g} kN/m",
                    color=EKSENEL_YUK_MAVISI, ha="center", fontsize=9)


def ciz_yatay_tepkiler(ax, model, reactions):
    """Yatay (normal kuvvet) mesnet tepkilerini yeşil yatay ok olarak ekle.

    Eksenel çözümden gelen yatay tepkiler mesnet düğümü hizasında kiriş
    ekseninin hemen altına çizilir (eksenel yük okları üsttedir). Ok kuvvet
    yönünü gösterir, etikette mutlak değer yazar; sıfır tepkiler atlanır.
    """
    total_L = float(sum(model.spans))
    y0, y1 = ax.get_ylim()
    dy = y1 - y0
    alen = 0.05 * total_L
    y = -0.05 * dy
    for r in reactions:
        H = r.get("H")
        if H is None or abs(H) < 1e-6:
            continue
        x = r["x"]
        sgn = 1 if H >= 0 else -1
        ax.annotate("", xy=(x + sgn * alen, y), xytext=(x, y),
                    arrowprops=dict(arrowstyle="-|>", color=NORMAL_KUVVET_YESILI,
                                    lw=2, mutation_scale=16))
        # Etiket ok ucunun ötesinde — mesnet glifinin üzerine binmesin.
        ax.text(x + sgn * alen * 1.15, y, f"{abs(H):g} kN",
                color=NORMAL_KUVVET_YESILI, ha="left" if sgn > 0 else "right",
                va="center", fontsize=9)
