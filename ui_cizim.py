"""
Şema çizim yardımcıları — sunum katmanı (Streamlit'e bağımlı DEĞİL).

PyCBA'nın çizicisi yalnız düşey yükleri ve düşey/moment tepkilerini tanır;
eksenel yükler ve yatay tepkiler burada matplotlib ile şemaya eklenir.
Hesap `core/`dedir; bu modül yalnızca çizer. `app.py` kullanır, ancak
Streamlit gerektirmediği için tarayıcısız da test edilebilir.
"""

from dataclasses import replace

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
# Öngörülmüş mesnet yer değiştirmesi etiketi. tab:purple (#9467bd) DEĞİL: şema
# her iki temada da beyaz "kağıt" üzerine çizilir ve tab:purple orada 3.7:1'de
# kalıyor — 8 punto etiket için yetersiz. Koyu mor 7.9:1 verir, mavi/yeşil/kırmızı
# ile karışmaz.
MESNET_COKMESI_MORU = "#6a3d9a"

# Şema çiziminin resim genişliği içindeki payı. Ölçeği SABİTLEMEK için kullanılır
# (bkz. _sabitle_olcek); değeri büyütmek şemayı büyütür ama figürü uzatır.
SEMA_KUTU_ORANI = 0.55

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
    # ŞEMADA EI'nin GÖRSEL KARŞILIĞI YOKTUR — bilerek. PyCBA, açıklıkların EI'si
    # farklı olduğu anda kirişi düz çizgi yerine derinliği EI^(1/3) ile değişen
    # gri bir GÖVDE olarak çizer (render.BeamPlotter._ei_depth_profile). Bu bizde
    # bilgi taşımıyor, üstelik bozuyor: gövde ±0.6·sh yer kapladığı için ara
    # mesnet gliflerini (-0.20·sh'de oturur), düğüm harflerini ve çökme
    # etiketlerini (-0.55·sh) yutuyor; EI'yi 30000'den 30001'e çekmek bile
    # kirişi kalın bir bara çeviriyor. Kullanıcı kesit GEOMETRİSİ değil, salt
    # sayı olarak EI giriyor; şemanın işi geometri ve yük yerleşimini
    # göstermek. Bu yüzden çiziciye EI'leri eşitlenmiş bir KOPYA verilir —
    # hesap gerçek EI'lerle yapılır, yalnız çizim etkilenmez.
    bp = BeamPlotter(build_beam(replace(model, EI=[1.0] * model.n_spans)),
                     loads=None)  # loads=None -> beam.LM
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
    # PyCBA eksen etiketini İngilizce yazar ("Distance along beam (m)");
    # Türkçe arayüzde İngilizce kalmasın diye katalogdan yeniden yazılır.
    if ax.get_xlabel():
        ax.set_xlabel(cevir(dil, "sema.eksen_x"))
    # Figür yüksekliği sabit (app.py 2.6/3.4 in); varsayılan bottom=0.11'de eksen
    # etiketi figür kenarında kırpılıyor. Legend varsa üst boşluğu _ciz_legend açar.
    ax.get_figure().subplots_adjust(bottom=0.20)
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
    # Legend ÖNCE: `subplots_adjust(top=...)` ile eksen kutusunu daraltıyor ve
    # şema eşit en-boy oranlı olduğu için kutunun GENİŞLİĞİ de değişiyor.
    # ciz_cokmeler etiket genişliğini bu ölçekten hesapladığından, sonradan
    # daralan kutu onu yanıltıp çakışmaya yol açıyordu.
    _ciz_legend(ax, model, reactions, dil)
    # Ölçek sabitleme, ylim'i etkileyen HER ŞEYDEN sonra ama çökme
    # etiketlerinden ÖNCE: etiket yerleşimi kutu genişliğinden ölçek çıkarıyor,
    # sonradan değişen kutu onu yanıltırdı.
    _sabitle_olcek(ax)
    ciz_cokmeler(ax, model, dil)


def _sabitle_olcek(ax):
    """Çizim ölçeğini içerikten bağımsız kıl: kutu genişliğini sabitle.

    PyCBA şemayı `set_aspect("equal", adjustable="box")` ile çizer; eşit ölçeği
    korumak için EKSEN KUTUSUNU daraltır. Düşey veri aralığı içeriğe göre
    değiştiği için (tekil yük oku uzun, yukarı yük alta taşar, moment yayı,
    tepki okları var/yok) kutu da onunla daralıp genişliyordu: aynı 8 punto
    yazı kirişin kâh 0.29 m'sini kâh 0.53 m'sini kaplıyor, kullanıcı "yazılar
    büyüdü, çizgiler kalınlaştı" diye görüyordu. Ölçüldü — 1.8 kat oynama.

    Çözüm: kutu genişliğini oran olarak SABİTLE, figür yüksekliğini veri
    en-boyundan türet. Böylece ölçek (metre/piksel) yalnız kiriş uzunluğuna
    bağlı kalır; yük tipi, tepki oku, çökme etiketi hiçbir şeyi kaydırmaz.
    Figürün yüksekliği içerikle değişir — ölçek yerine BOY esner.
    """
    fig = ax.get_figure()
    sol = (1.0 - SEMA_KUTU_ORANI) / 2.0  # kutu yatayda ortalanır
    fig.subplots_adjust(left=sol, right=sol + SEMA_KUTU_ORANI)
    # `original=True` ŞART: `get_position()` varsayılanı, en-boy oranı için
    # matplotlib'in daralttığı AKTİF kutuyu verir. Onu kullanmak denklemi kendi
    # kendini doğrulayan bir sabit noktaya çevirip yüksekliği hiç değiştirmiyor.
    # Bize subplots_adjust ile kurulan özgün dikey pay (top − bottom) gerekli.
    kutu = ax.get_position(original=True)
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    gen_in = fig.get_size_inches()[0] * SEMA_KUTU_ORANI
    yuk_in = gen_in * (y1 - y0) / (x1 - x0)  # eşit ölçek için gereken yükseklik
    fig.set_size_inches(fig.get_size_inches()[0], yuk_in / kutu.height)


def _ciz_legend(ax, model, reactions, dil=None):
    """Şemadaki renk kodlarını açıklayan legend ekle (yalnız çizilen kategoriler).

    Renk dili: kırmızı = düşey yük, mavi = eksenel yük, yeşil = mesnet tepkisi
    (düşey/moment/yatay). PyCBA `render_mpl` yükleri tab:red, `render_reactions_mpl`
    tepkileri tab:green çizer; eksenel yük mavi + yatay tepki yeşil bu modülde
    eklenir. Proxy handle'lar boş veriyle kurulur (eksen sınırlarını bozmaz).
    """
    girisler = []
    if any(ld.kind not in AXIAL_KINDS for ld in model.loads):
        girisler.append(("tab:red", "v", cevir(dil, "sema.legend.dusey")))
    if any(ld.kind in AXIAL_KINDS for ld in model.loads):
        girisler.append((EKSENEL_YUK_MAVISI, ">", cevir(dil, "sema.legend.eksenel")))
    tepki_var = bool(reactions) and any(
        (r.get("V") and abs(r["V"]) > 1e-6)
        or (r.get("M") and abs(r["M"]) > 1e-6)
        or (r.get("H") and abs(r["H"]) > 1e-6)
        for r in reactions
    )
    if tepki_var:
        girisler.append((NORMAL_KUVVET_YESILI, "^", cevir(dil, "sema.legend.tepki")))
    if any(abs(d) > 1e-12 for d in model.settlements.values()):
        girisler.append((MESNET_COKMESI_MORU, "d", cevir(dil, "sema.legend.cokme")))
    if not girisler:
        return
    # Glif renkten BAĞIMSIZ ikinci bir ayırt edicidir: kırmızı (düşey yük) ile
    # yeşil (tepki) deutan görüşte ayrışmıyor (ΔE 3.9, eşik 6). Glifler şemadaki
    # ok yönleriyle eşleşir — yük aşağı (v), tepki yukarı (^), eksenel yatay (>).
    handles = [
        Line2D([], [], color=c, lw=2.2, marker=m, markersize=7, label=ad)
        for c, m, ad in girisler
    ]
    # Legend eksenin DIŞINDA, üstte yatay durur: "lower right" içeride sağdaki
    # mesnet tepki etiketinin üstüne biniyordu.
    ax.get_figure().subplots_adjust(top=0.80)
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.01),
              ncols=len(handles), fontsize=8, frameon=False)


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


def ciz_cokmeler(ax, model, dil=None):
    """Mesnet çökmelerini mesnet glifinin altına mor etiket olarak yaz.

    Çökme bir KUVVET değil, dayatılmış yer değiştirmedir; ok yerine yön oku +
    değer etiketi kullanılır (mor: yük kırmızısından, tepki yeşilinden ve
    eksenel maviden ayrı; "mm" birimi de şemada yalnız burada geçer).

    Yerleşim, kirişin ALTINDAKİ boş şerittir: yükler kirişin üstünde, mesnet
    glifi doğrudan mesnedin altında (≈ -1.5·sh), ölçü çizgisi -2.3·sh ve tepki
    okları -1.7·sh'den aşağıda durur; `sh = 0.05·L` çizicinin glif birimidir
    (pycba.render.BeamPlotter.render_mpl). Etiket mesnedin yanına kaydırılır ki
    glifin üstüne binmesin — normalde sağa, grafik alanından taşacaksa sola.

    ÇAKIŞMA (yaşanmış; tahmin etme, ölçerek doğrula): etiket genişliği punto
    cinsinden sabit, açıklık ise açıklık sayısı arttıkça inç olarak daralır —
    ayrıca sola dönen etiket komşusuyla aynı açıklığı paylaşır. Bu yüzden
    genişlik veri birimine çevrilip (eksenin inç genişliğinden; çizici
    gerekmez) iki satıra dağıtılır: üst satır -0.55·sh, alt satır -1.25·sh.
    Üst satır DÜĞÜM HARFLERİYLE (A, B, …) paylaşılır, onlar da engel sayılır.
    İki satır da yetmezse punto küçültülür (8 → 7 → 6). Üçüncü satır YOK:
    altta tepki okları (-1.7·sh) ve açıklık ölçü çizgisi (-2.3·sh) var.

    Bilinen sınır: 10 açıklık + her mesnette çökme + tepki okları bir çift
    etikette çakışma bırakır. Kovalanmadı — o yoğunlukta PyCBA'nın kendi tepki
    etiketleri ve mesnet harfleri de üst üste biniyor, şema zaten okunmuyor.

    Model GENİŞLETİLMİŞ olmalıdır (ciz_sema öyle çağırır): `expand()` çökmeleri
    de yeni düğüm numaralandırmasına taşır.
    """
    kalemler = [(n, -float(d) * 1000.0)  # arayüzdeki işaret: + aşağı
                for n, d in sorted(model.settlements.items())
                if abs(float(d)) > 1e-12]
    if not kalemler:
        return
    node_x = np.concatenate([[0.0], np.cumsum(model.spans)])
    sh = 0.05 * float(node_x[-1])
    # Etiket = yön oku + değer. Birim ("mm") legend'dadır; şemada mesnet başına
    # düşen yatay yer açıklık sayısıyla daraldığı için her karakter pahalı.
    # Çeviri gerektirmez, katalogda anahtarı yok.
    metinler = [f"{'↓' if mm > 0 else '↑'} {abs(mm):g}" for _, mm in kalemler]

    # Metnin veri birimindeki genişliği: eksenin inç genişliğinden ölçek çıkarılır.
    # `apply_aspect()` ÖNCE, `get_position(original=False)` sonra: şema eşit
    # en-boy oranıyla (`adjustable="box"`) çizilir, yani matplotlib veri
    # sınırlarını değil EKSEN KUTUSUNU daraltır — hele tepki okları ylim'i
    # aşağı büyüttükten sonra. `get_position()` özgün (daraltılmamış) kutuyu
    # verdiği için ölçek %50'ye varan hatayla çıkıyor, üç açıklıkta "sığar"
    # deyip etiketler çakışıyordu.
    # 0.70 em: DejaVu Sans'ta ölçülen ortalama karakter genişliği (0.681) +
    # küçük emniyet payı; kesin olması gerekmiyor, yalnız satır kararını verir.
    fig = ax.get_figure()
    ax.apply_aspect()
    eksen_inc = fig.get_size_inches()[0] * ax.get_position(original=False).width
    veri_inc = (ax.get_xlim()[1] - ax.get_xlim()[0]) / eksen_inc
    satir_y = (-0.55 * sh, -1.25 * sh)

    # ÜST satırı düğüm harfleriyle (A, B, …) paylaşıyoruz: PyCBA onları tam bu
    # yükseklikte, mesnedin 0.8·sh soluna (sağ uçta sağına) yazar. Etiketleri
    # yalnız birbirleriyle kıyaslamak yetmiyordu — altı açıklıkta etiketler
    # harflerin üstüne biniyordu. Harfler burada engel olarak listelenir; alt
    # satırda harf yok, çakışan etiket oraya iner.
    harf_w = 0.70 * 9 / 72.0 * veri_inc  # tek karakter, PyCBA'da 9 punto kalın
    harfler = []
    for i, sup in enumerate(model.supports):
        if sup == "free":  # çizilmeyen mesnedin harfi de yok (bkz. ciz_sema)
            continue
        hx = float(node_x[i])
        harfler.append((hx + 0.8 * sh, hx + 0.8 * sh + harf_w)
                       if i == len(node_x) - 1
                       else (hx - 0.8 * sh - harf_w, hx - 0.8 * sh))

    def _yerlesim(punto):
        """Etiketleri iki satıra dağıt; (yerler, çakışma sayısı) döndür."""
        yerler, satir_sonu, cakisma = [], [-np.inf, -np.inf], 0

        def _bos(satir, x0, x1):
            if x0 <= satir_sonu[satir] + 0.2 * sh:
                return False
            return satir != 0 or not any(a < x1 and x0 < b for a, b in harfler)

        for (n, _mm), metin in zip(kalemler, metinler):
            w = 0.70 * punto / 72.0 * len(metin) * veri_inc
            # Mesnet glifi ±0.5·sh, altındaki zemin taraması 1.5·sh geniştir;
            # 1.0·sh kaydırma etiketi ikisinin de dışında tutar. Daraltmayı
            # deneme — 0.8·sh'de etiket glifin üstüne biniyordu; sıkışıklık
            # satır/punto ile çözülür, kaydırmayı kısarak değil.
            # Kural: etiket mesnedin SAĞINA yazılır; grafik alanından taşacaksa
            # (sağ uç mesnedi ve çok açıklıkta sondan bir önceki) sola döner.
            # Yalnız "sağ uç" diye özel durum yazmak yetmiyordu: 10 açıklıkta
            # sondan bir önceki etiket eksenin dışına taşıp kırpılıyordu.
            x_dugum = float(node_x[n - 1])
            sola = x_dugum + sh + w > ax.get_xlim()[1]
            x = x_dugum + (-sh if sola else sh)
            x0 = x - w if sola else x
            uygun = [i for i in (0, 1) if _bos(i, x0, x0 + w)]
            if uygun:
                satir = uygun[0]
            else:  # ikisi de dolu: az taşanı seç, çakışmayı say
                satir = int(np.argmin(satir_sonu))
                cakisma += 1
            satir_sonu[satir] = x0 + w
            yerler.append((x, satir_y[satir], metin, "right" if sola else "left"))
        return yerler, cakisma

    for punto in (8, 7, 6):
        yerler, cakisma = _yerlesim(punto)
        if not cakisma:
            break
    for x, y, metin, hiza in yerler:
        ax.text(x, y, metin, color=MESNET_COKMESI_MORU, ha=hiza, va="center",
                fontsize=punto, zorder=9)


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
    # Mesnet harfleri (A, B, …) kiriş ekseninin hemen altında duruyor; ok satırı
    # onların altına indirilir, yoksa A mesnedinde etiket harfin üstüne biniyor.
    y = -0.10 * dy
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
        # HESAPLANAN tepki: PyCBA'nın düşey tepki etiketleriyle aynı hassasiyet
        # (2 hane). ":g" burada "33.3333 kN" gibi okunmaz sayılar üretiyordu.
        # Uygulanan yüklerde ":g" korunur — onlar kullanıcının girdiği tam sayılar.
        ax.text(x + sgn * alen * 1.15, y, f"{abs(H):.2f} kN",
                color=NORMAL_KUVVET_YESILI, ha="left" if sgn > 0 else "right",
                va="center", fontsize=9)
