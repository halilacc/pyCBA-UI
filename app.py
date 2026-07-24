"""
PyCBA Web Arayüzü — Streamlit.

Yalnızca sunum katmanı: model kurulumu ve çözüm `core/` paketindedir.
Çalıştırma: .venv\\Scripts\\streamlit run app.py
"""

import matplotlib.pyplot as plt
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core import (
    AXIAL_KINDS, BeamModel, Load, LOAD_TYPES, SUPPORT_TYPES,
    check_load_position, solve, SolverError,
)
from ui_cizim import NORMAL_KUVVET_YESILI, ciz_sema
from ui_tema import enjekte_tema, hero_baslik, tepki_tablosu

SUPPORT_LABELS = {
    "pin": "Mafsal (pin)",
    "roller": "Kayıcı (roller)",
    "fixed": "Ankastre (fixed)",
    "free": "Serbest (free)",
}

# Yük parametresi -> (etiket, birim)
PARAM_LABELS = {
    "w": ("Yayılı yük w", "kN/m"),
    "w1": ("Başlangıç şiddeti w₁", "kN/m"),
    "w2": ("Bitiş şiddeti w₂", "kN/m"),
    "P": ("Yük P", "kN"),
    "M": ("Moment M", "kNm"),
    "a": ("Konum a — açıklığın sol ucundan", "m"),
    "c": ("Yayılı uzunluk c", "m"),
    "N": ("Eksenel yük N (+ sağa)", "kN"),
    "n": ("Eksenel yayılı yük n (+ sağa)", "kN/m"),
}

# Yük tipine göre konum ipucu
KIND_HINTS = {
    "udl": "Tüm açıklığa yayılır; konum girilmez.",
    "point": "a: yükün açıklığın sol ucundan uzaklığı (örn. orta nokta için L/2).",
    "partial_udl": "a: sol uçtan başlangıç uzaklığı, c: yükün yayıldığı uzunluk (a+c ≤ L).",
    "moment": "a: momentin açıklığın sol ucundan uzaklığı.",
    "trapezoid": "a=0 ve c=0 girilirse tüm açıklığa yayılır; kısmi için a ve c verin.",
    "axial_point": "Kiriş eksenine (x) paralel tekil yük; + değer sağa. a: sol uçtan uzaklık. Şemada mavi yatay ok, sonuçta N diyagramı.",
    "axial_udl": "Kiriş eksenine (x) paralel, tüm açıklığa yayılı yük; + değer sağa. Şemada mavi yatay oklar, sonuçta N diyagramı.",
}


st.set_page_config(page_title="PyCBA Kiriş Analizi", page_icon="🏗️", layout="wide")
# Tema modu: kenar çubuğundaki toggle "tema_gece"yi yazar; burada (rerun'da)
# okunup CSS enjekte edilir. Toggle enjeksiyondan sonra çizilir ama Streamlit
# her etkileşimde baştan çalıştığı için değer bir sonraki rerun'da yansır.
mod = "gece" if st.session_state.get("tema_gece", False) else "aydinlik"
karanlik = mod == "gece"
enjekte_tema(mod)
hero_baslik(
    "Sürekli Kiriş Analizi",
    "PyCBA çekirdeğiyle mesnet tepkileri, kesit tesirleri ve sehim — anında, "
    "etkileşimli diyagramlarla.",
)

if "loads" not in st.session_state:
    st.session_state.loads = []  # list[Load]
# Ekleme formu alanlarının anahtarına giren sayaç: bir yük eklenince artırılır ki
# widget'lar yeniden kurulup (remount) boşalsın. Form içindeki number_input'un
# frontend değeri submit sonrası kalıcı olduğundan session_state'i silmek alanı
# temizlemez; anahtarı değiştirmek temizler.
st.session_state.setdefault("add_nonce", 0)
# Açıklık içi mafsallar: (açıklık no, sol uçtan a [m]) çiftleri.
st.session_state.setdefault("span_hinges", [])
st.session_state.setdefault("mh_nonce", 0)

# ---------------------------------------------------------------- girdi paneli
with st.sidebar:
    # Tema toggle: key "tema_gece" — üstte okunup CSS moduna karar verilir.
    st.toggle("🌙 Gece modu", key="tema_gece")

    st.header("1. Geometri")
    n_spans = st.number_input("Açıklık sayısı", min_value=1, max_value=10, value=2)

    spans, EI = [], []
    for i in range(n_spans):
        c1, c2 = st.columns(2)
        spans.append(
            c1.number_input(
                f"L{i + 1} [m]", min_value=0.1, value=6.0, step=0.5,
                key=f"span_{i}",
            )
        )
        EI.append(
            c2.number_input(
                f"EI{i + 1} [kNm²]", min_value=1.0, value=30_000.0,
                step=1000.0, format="%.0f", key=f"ei_{i}",
            )
        )

    st.header("2. Mesnetler")
    supports = []
    for i in range(n_spans + 1):
        default = "pin" if i in (0, n_spans) else "roller"
        supports.append(
            st.selectbox(
                f"Düğüm {i + 1}", SUPPORT_TYPES,
                index=SUPPORT_TYPES.index(default),
                format_func=SUPPORT_LABELS.get,
                key=f"sup_{i}",
            )
        )

    # Gerber kirişi: ara düğümlere iç mafsal. Uç düğümlerde mafsal anlamsızdır
    # (orada tek eleman var; mesnet tipi zaten belirler), bu yüzden seçenekler
    # yalnız 2..n_spans. Anahtar açıklık sayısına bağlı — açıklık azalınca artık
    # var olmayan düğüm no'su seçili kalmasın.
    hinges = st.multiselect(
        "İç mafsallı düğümler (Gerber)",
        options=list(range(2, n_spans + 1)),
        format_func=lambda h: f"Düğüm {h}",
        help="Seçilen düğümde kiriş moment aktarmaz; şemada içi boş daire ile gösterilir.",
        key=f"hinges_{n_spans}",
    )

    # Açıklık İÇİNDE mafsal: kullanıcı (açıklık, sol uçtan a) verir; core bunu
    # açıklığı bölüp araya mesnetsiz düğüm koyarak çözer (BeamModel.expand).
    # Kullanıcının açıklık ve yük numaralandırması değişmez.
    with st.expander("Açıklık içi mafsal"):
        st.caption(
            "Mafsalı mesnet hizasında değil, açıklığın ortasında bir noktada "
            "istiyorsan buradan ekle. Açıklık o noktadan otomatik bölünür."
        )
        # Açıklık no form DIŞINDA (yük formuyla aynı desen ve aynı nedenle):
        # konum widget'ının key'i açıklık no'ya bağlı olduğundan, açıklık no form
        # İÇİNDE olsaydı gönderim anında key değişir, konum widget'ı yeniden kurulur
        # ve kullanıcının yazdığı değer sessizce 0'a düşerdi. Dışarıda olunca
        # açıklık değişimi anında rerun tetikler; hem a'nın max_value sınırı hem
        # de key, kullanıcı konumu yazmadan ÖNCE güncellenmiş olur.
        mh_span = int(st.number_input(
            "Mafsalın olduğu açıklık no", min_value=1, max_value=n_spans,
            value=1, step=1, key=f"mh_span_{n_spans}",
        ))
        L_mh = float(spans[mh_span - 1])
        with st.form("mafsal_ekle_form"):
            # Sayaç yük formundaki `add_nonce` ile aynı işi görür: mafsal eklenince
            # anahtar değişir, alan boş (placeholder "0") yeniden kurulur.
            mh_key = f"mh_a_{mh_span}_{L_mh:g}_{st.session_state.mh_nonce}"
            mh_a = st.number_input(
                f"Konum a [m] — sol uçtan (0 < a < {L_mh:g})",
                min_value=0.0, max_value=L_mh, value=None,
                step=0.25, placeholder="0", key=mh_key,
            )
            mh_ekle = st.form_submit_button("➕ Mafsal ekle", width="stretch")
        if mh_ekle:
            a_val = 0.0 if mh_a is None else float(mh_a)
            if not (0 < a_val < L_mh):
                st.error(
                    f"Konum açıklığın içinde olmalı (0 < a < {L_mh:g} m). "
                    "Mesnet hizasındaki mafsal için üstteki düğüm seçimini kullan."
                )
            elif (mh_span, a_val) in st.session_state.span_hinges:
                st.error("Bu mafsal zaten tanımlı.")
            else:
                st.session_state.span_hinges.append((mh_span, a_val))
                st.session_state.pop(mh_key, None)
                st.session_state.mh_nonce += 1
                st.rerun()
        # Açıklık sayısı/uzunluğu küçültülünce geçersiz kalan mafsalları at —
        # yoksa model sürekli doğrulama hatası verip arayüzü kilitler.
        st.session_state.span_hinges = [
            (s, a) for s, a in st.session_state.span_hinges
            if 1 <= s <= n_spans and 0 < a < float(spans[s - 1])
        ]
        for j, (s, a) in enumerate(st.session_state.span_hinges):
            lc1, lc2 = st.columns([3, 1])
            lc1.write(f"Açıklık {s} · a = {a:g} m")
            if lc2.button("🗑️", key=f"mh_sil_{j}"):
                st.session_state.span_hinges.pop(j)
                st.rerun()

    st.header("3. Yükler")
    # Önce hangi açıklığa yük konacağı, sonra yük tipi seçilir (doğal akış:
    # "nereye" → "ne"). Anahtar açıklık sayısına bağlı: kullanıcı açıklık sayısını
    # küçültünce eski (artık max_value dışında kalabilecek) değer taşınmaz — aksi
    # halde Streamlit "value > max_value" istisnası fırlatır. (a/c widget'larıyla
    # tutarlı "key'i bağla" deseni.)
    load_span = st.number_input(
        "Açıklık no", min_value=1, max_value=n_spans, value=1,
        key=f"load_span_{n_spans}",
    )
    L_sel = float(spans[load_span - 1])
    kind = st.selectbox(
        "Yük tipi", list(LOAD_TYPES), format_func=lambda k: LOAD_TYPES[k][1],
    )
    st.caption(f"{KIND_HINTS[kind]}  (Seçili açıklık: L = {L_sel:g} m)")
    # Parametreler bir form içinde toplanır: elle YAZILAN değerler (özellikle konum
    # a) ancak "Yük ekle"ye basınca topluca gönderilir. Form dışında number_input'a
    # yazılan değer widget odağı değişene kadar kaydedilmediğinden, yazıp butona
    # basınca eski (0) değer okunuyordu; +/- adımı ise anında commit ettiği için
    # çalışıyordu. Yük tipi ve açıklık no form DIŞINDA kaldı ki değişince a'nın
    # max_value=L sınırı ve parametre alanları anında yenilensin.
    with st.form("yuk_ekle_form"):
        values, param_keys = [], []
        for p in LOAD_TYPES[kind][2]:
            label, unit = PARAM_LABELS[p]
            if p in ("a", "c"):
                # Konum parametreleri açıklık uzunluğunu aşamaz. Anahtar açıklığa ve
                # L'ye bağlı: açıklık/uzunluk değişince eski (artık geçersiz olabilecek)
                # değer taşınmaz.
                kw = dict(min_value=0.0, max_value=L_sel, step=0.25)
                key = f"lv_{kind}_{p}_{load_span}_{L_sel:g}_{st.session_state.add_nonce}"
            else:
                kw = dict(step=1.0)
                key = f"lv_{kind}_{p}_{st.session_state.add_nonce}"
            param_keys.append(key)
            # value=None: alan "0.00" yerine BOŞ (placeholder "0") başlar. Aksi halde
            # kullanıcı "0.00" önekini seçip silmeden "1000" yazınca alana "0.001000"
            # (=0.001 gibi saçma bir değer) giriyordu. Boş bırakılan alan aşağıda 0.0
            # sayılır; tüm şiddetler 0 ise zaten uyarı verilir.
            values.append(
                st.number_input(
                    f"{label} [{unit}]", value=None, placeholder="0", key=key, **kw
                )
            )
        submitted = st.form_submit_button("➕ Yük ekle", width="stretch", type="primary")
    # Boş bırakılan (None) alanları 0.0 kabul et — doğrulama/çözüm float bekler.
    values = [0.0 if v is None else v for v in values]
    if submitted:
        # Şiddet parametreleri (konum a/c dışındakiler) tümü 0 ise yük eklemek
        # anlamsızdır; sessizce 0'lık yük eklemek yerine uyar.
        siddetler = [v for p, v in zip(LOAD_TYPES[kind][2], values) if p not in ("a", "c")]
        pos_err = check_load_position(kind, values, L_sel)
        if all(abs(v) < 1e-12 for v in siddetler):
            st.error("Yük şiddeti 0 — sıfırdan farklı bir değer girin.")
        elif pos_err:
            st.error(pos_err)
        else:
            st.session_state.loads.append(Load(span=load_span, kind=kind, values=values))
            # Sayaç artınca alan anahtarları değişir → widget'lar boş (placeholder
            # "0") yeniden kurulur; eski anahtarlar session_state'te birikmesin diye
            # temizlenir. Böylece sonraki yük yine temiz başlar (üstüne yazma tuzağı yok).
            for k in param_keys:
                st.session_state.pop(k, None)
            st.session_state.add_nonce += 1
            st.rerun()

    # -------------------------------------------------------------- görünüm
    # Hangi grafiklerin çizileceği. Kenar çubuğunda tutulur ki her durumda
    # (yük yokken, çözüm hata verirken de) erişilebilsin; ana alandaki çizim
    # bloklarının hepsi bu bayrakları okur.
    st.header("4. Görünüm")
    st.caption("Kapatılan grafik hiç çizilmez; sayısal sonuçlar etkilenmez.")
    # Normal kuvvet grafiği yalnız eksenel yük varken anlamlı — yoksa toggle da
    # gösterilmez (kullanıcı boş bir anahtarla uğraşmasın).
    has_axial = any(ld.kind in AXIAL_KINDS for ld in st.session_state.loads)
    goster_sema = st.toggle("Kiriş şeması", value=True, key="goster_sema")
    goster_N = (
        st.toggle("Normal kuvvet (N)", value=True, key="goster_N")
        if has_axial else False
    )
    goster_V = st.toggle("Kesme kuvveti (V)", value=True, key="goster_V")
    goster_M = st.toggle("Moment (M)", value=True, key="goster_M")
    goster_D = st.toggle("Sehim", value=True, key="goster_D")

# --------------------------------------------------------------- yük listesi
st.subheader("Tanımlı yükler")
if not st.session_state.loads:
    st.info("Henüz yük eklenmedi — kenar çubuğundan ekleyin.")
else:
    st.caption("Bir yükü düzenlemek için başlığına tıklayıp açın.")
    # Her yük açılır bir düzenleme formu: açıklık ve değerler değiştirilip
    # kaydedilebilir; hatalı girişte sil-ekle gerekmez. Yük tipini satır-içi
    # değiştirmiyoruz (nadir; bunun için silip yeniden ekleyin). Widget key'leri
    # yükün İÇERİĞİNE bağlı (indeks + span + değerler): bir yük silinip indeksler
    # kayınca veya kaydedince key değişir, alanlar güncel değerle yeniden kurulur;
    # düzenleme sırasında (kayıtlı içerik sabitken) key sabit kalıp yazılanı korur.
    for i, ld in enumerate(st.session_state.loads):
        _, name, params = LOAD_TYPES[ld.kind]
        desc = ", ".join(
            f"{p}={v:g} {PARAM_LABELS[p][1]}" for p, v in zip(params, ld.values)
        )
        sig = f"{i}_{ld.span}_" + "-".join(f"{v:g}" for v in ld.values)
        with st.expander(f"**{i + 1}.** {name} — Açıklık {ld.span} — {desc}"):
            with st.form(f"duzenle_form_{sig}"):
                new_span = int(
                    st.number_input(
                        "Açıklık no", min_value=1, max_value=n_spans,
                        value=ld.span, step=1, key=f"edit_span_{sig}",
                    )
                )
                new_values = []
                # Konum sınırı seçili açıklığın L'sine bağlı (ekleme formuyla aynı
                # canlı clamp); açıklık değişince max_value de anında güncellenir.
                L_edit = float(spans[new_span - 1])
                for j, p in enumerate(params):
                    label, unit = PARAM_LABELS[p]
                    if p in ("a", "c"):
                        kw = dict(min_value=0.0, max_value=L_edit, step=0.25)
                        # Değer yeni açıklığın L'sini aşmasın (aksi halde Streamlit
                        # hata verir); anahtar new_span'e bağlı, açıklık değişince
                        # konum widget'ı clamp'lenmiş değerle yeniden kurulur.
                        val = min(max(float(ld.values[j]), 0.0), L_edit)
                        key = f"edit_val_{p}_{sig}_{new_span}"
                    else:
                        kw = dict(step=1.0)
                        val = float(ld.values[j])
                        key = f"edit_val_{p}_{sig}"
                    new_values.append(
                        st.number_input(f"{label} [{unit}]", value=val, key=key, **kw)
                    )
                bc1, bc2 = st.columns(2)
                kaydet = bc1.form_submit_button("💾 Kaydet", width="stretch")
                sil = bc2.form_submit_button("🗑️ Sil", width="stretch")
            if sil:
                st.session_state.loads.pop(i)
                st.rerun()
            if kaydet:
                # Yeni açıklığın L'sine göre konum doğrula (açıklık değişmiş olabilir).
                pos_err = check_load_position(
                    ld.kind, new_values, float(spans[new_span - 1])
                )
                siddetler = [
                    v for p, v in zip(params, new_values) if p not in ("a", "c")
                ]
                if all(abs(v) < 1e-12 for v in siddetler):
                    st.error("Yük şiddeti 0 olamaz — silmek için 🗑️ kullanın.")
                elif pos_err:
                    st.error(pos_err)
                else:
                    st.session_state.loads[i] = Load(
                        span=new_span, kind=ld.kind, values=new_values
                    )
                    st.rerun()

# --------------------------------------------------------------------- çözüm
model = BeamModel(
    spans=spans, EI=EI, supports=supports,
    loads=st.session_state.loads, hinges=hinges,
    span_hinges=list(st.session_state.span_hinges),
)

errors = model.validate()
if errors:
    for e in errors:
        st.error(e)
    st.stop()

# Kiriş şeması: mesnetler + yükler konumlarıyla çizilir, model her değiştiğinde
# güncellenir — kullanıcı yükü nereye etki ettirdiğini burada görür. Çözüm
# yapılabiliyorsa mesnet tepkileri de ok olarak şemanın üzerine eklenir.
# Şema üç ayrı akışta (yük yok / çözülemedi / normal) çizildiği için tek
# yardımcıya alındı; "Görünüm" toggle'ı kapalıysa hiçbirinde çizilmez.
def _sema_ciz(reactions=None, yukseklik=2.6):
    if not goster_sema:
        return
    st.subheader("Kiriş şeması")
    fig_schema, ax_schema = plt.subplots(figsize=(10, yukseklik))
    ciz_sema(ax_schema, model, reactions)
    st.pyplot(fig_schema, width="stretch")
    plt.close(fig_schema)


# Yük yoksa çözüm (dolayısıyla tepki) yok: yalnızca şemayı çiz ve dur.
if not st.session_state.loads:
    _sema_ciz()
    st.info("Sonuçlar ve mesnet tepkileri için en az bir yük ekleyin.")
    st.stop()

# Yük var: tepki oklarını çizebilmek için önce çöz. Çözülemezse şemayı yine de
# yükleriyle göster ve hatayı bildir.
try:
    result = solve(model)
except SolverError as e:
    _sema_ciz()
    st.error(str(e))
    st.stop()

# Şema + mesnet tepki okları (oklar/etiketler için biraz daha yüksek figür).
_sema_ciz(result["reactions"], yukseklik=3.4)

# ------------------------------------------------------------------ sonuçlar
st.subheader("Sonuçlar")

# (has_axial kenar çubuğunda "4. Görünüm" için zaten hesaplandı.)
# Metrik kartları görünüm toggle'larından etkilenmez: sayısal özet kompakttır ve
# grafiği kapatan kullanıcı da ekstrem değerleri görmek ister.

# Tutarlılık için her büyüklükte işaretli maks + min gösterilir (yalnız mutlak
# değil): negatif ekstremler mühendislik açısından da anlamlıdır (örn. mesnet
# üstü negatif moment). Büyük sayı maks; caption'da ekstremlerin kiriş üzerindeki
# konumu (x) da verilir — argmax/argmin saf sunum hesabı, core değişmez.
def _ekstrem_konum(x_arr, y_arr, en_buyuk):
    """Ekstremin (maks/min) apsis konumunu [m] döndür."""
    idx = int(y_arr.argmax() if en_buyuk else y_arr.argmin())
    return float(x_arr[idx])

def _kart(col, baslik, birim, xd, yd, olcek=1.0):
    vmaks, vmin = float(yd.max()) * olcek, float(yd.min()) * olcek
    col.metric(f"Maks. {baslik} [{birim}]", f"{vmaks:.2f}")
    col.caption(
        f"@ x = {_ekstrem_konum(xd, yd, True):.2f} m  \n"
        f"Min. {vmin:.2f} @ x = {_ekstrem_konum(xd, yd, False):.2f} m"
    )

def _diyagram_csv(basliklar, *diziler):
    """Diyagram dizilerini (aynı apsis üzerinde) CSV metnine çevir."""
    satirlar = [",".join(basliklar)]
    for degerler in zip(*diziler):
        satirlar.append(",".join(f"{float(v):.6g}" for v in degerler))
    return "\n".join(satirlar) + "\n"

cols = st.columns(4 if has_axial else 3)
_kart(cols[0], "moment", "kNm", result["x"], result["M"])
_kart(cols[1], "kesme", "kN", result["x"], result["V"])
_kart(cols[2], "sehim", "mm", result["x"], result["D"], olcek=1000.0)
if has_axial:
    _kart(cols[3], "normal", "kN", result["xN"], result["N"])

# Kesit tesiri diyagramları TEK figürde, sıra: Normal · Kesme · Moment · Sehim
# (Normal yalnız eksenel yük varsa; ayrı grafik çıkmaz). PyCBA'nın sabit 3-panelli
# plotly figürü yerine result dizilerinden kurulur ki panel sayısı/sırası dinamik
# olsun ve N aynı x eksenini paylaşsın. Renk/dolgu/moment-ekseni-ters konvansiyonu
# PyCBA ile aynı tutulur.
_KIRMIZI, _KIRMIZI_DOLGU = "#d62728", "rgba(214,39,40,0.12)"
# Grafik moda göre renklenir; zemin şeffaf bırakılıp kart yüzeyi görünür.
_g_yazi = "#E9E7E2" if karanlik else "#1C1B19"
_g_izgara = "rgba(255,255,255,0.10)" if karanlik else "rgba(28,27,25,0.08)"
_g_sifir = "rgba(233,231,226,0.55)" if karanlik else "rgba(28,27,25,0.45)"
# Paneller "4. Görünüm" toggle'larına göre süzülür; kapatılan panel hiç
# eklenmediği için figür yüksekliği ve x ekseni başlığı kendiliğinden uyar.
paneller = []
if has_axial and goster_N:
    # Şema ile ortak yeşil; ince çizgi + düşük opaklık dolgu (dataviz).
    paneller.append(
        ("Normal", "kN", result["xN"], result["N"],
         NORMAL_KUVVET_YESILI, "rgba(44,160,44,0.15)", False)
    )
# (ad, birim, x, y, çizgi_rengi, dolgu_rgba|None, y_ekseni_ters)
if goster_V:
    paneller.append(
        ("Kesme", "kN", result["x"], result["V"], _KIRMIZI, _KIRMIZI_DOLGU, False)
    )
if goster_M:
    paneller.append(
        ("Moment", "kNm", result["x"], result["M"], _KIRMIZI, _KIRMIZI_DOLGU, True)
    )
if goster_D:
    paneller.append(
        ("Sehim", "mm", result["x"], result["D"] * 1000.0, _KIRMIZI, None, False)
    )
n_panel = len(paneller)
if n_panel == 0:
    # Hepsi kapalı: boş figür çizmek yerine nereden açılacağını söyle.
    st.info(
        "Tüm diyagramlar kapalı — kenar çubuğundaki **4. Görünüm** bölümünden "
        "açabilirsin. Metrikler, mesnet tepkileri ve CSV indirme etkilenmez."
    )
else:
    fig = make_subplots(rows=n_panel, cols=1, shared_xaxes=True, vertical_spacing=0.05)
    for i, (ad, birim, xr, yr, renk, dolgu, ters) in enumerate(paneller, start=1):
        fig.add_trace(
            go.Scatter(
                x=xr, y=yr, mode="lines", name=ad,
                line=dict(color=renk, width=1.6),
                fill="tozeroy" if dolgu else None, fillcolor=dolgu,
                hovertemplate=f"{ad}: %{{y:.4g}} {birim}<extra></extra>",
            ),
            row=i, col=1,
        )
        fig.add_hline(y=0, line=dict(color=_g_sifir, width=1), row=i, col=1)
        fig.update_yaxes(title_text=f"{ad} [{birim}]", row=i, col=1)
        if ters:  # moment: sagging-pozitif aşağıda (PyCBA konvansiyonu korunur)
            fig.update_yaxes(autorange="reversed", row=i, col=1)
    fig.update_xaxes(title_text="Kiriş boyunca konum [m]", row=n_panel, col=1)
    # fixedrange=True: dokunmatik ekranda grafik zoom/pan/pinch yapmaz — parmak
    # hareketi sayfayı kaydırır, grafiği değil. Hover ipuçları çalışmaya devam eder.
    fig.update_xaxes(gridcolor=_g_izgara, zerolinecolor=_g_sifir, linecolor=_g_izgara, fixedrange=True)
    fig.update_yaxes(gridcolor=_g_izgara, zerolinecolor=_g_sifir, fixedrange=True)
    fig.update_layout(
        # Başlık rengi açıkça verilir; aksi halde Streamlit'in plotly şablonu koyu
        # bırakıp gece modunda okunmaz kılıyordu.
        title=dict(text="Kesit Tesirleri Diyagramları", y=0.99, yanchor="top",
                   font=dict(color=_g_yazi)),
        margin=dict(t=70),
        height=240 * n_panel + 90,  # panel başına ~240 px; başlık/eksen için pay
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=_g_yazi),
    )
    # displayModeBar=False: zoom/pan araç çubuğu gizli (fixedrange ile zaten
    # işlevsiz) — hem mobilde başlıkla çakışmasını önler hem arayüzü sadeleştirir.
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
st.download_button(
    "⬇️ Diyagram verileri (CSV)",
    _diyagram_csv(
        ["x [m]", "Moment [kNm]", "Kesme [kN]", "Sehim [mm]"],
        result["x"], result["M"], result["V"], result["D"] * 1000.0,
    ),
    file_name="diyagram_moment_kesme_sehim.csv",
    mime="text/csv",
)
if has_axial:
    # N kendi apsis dizisini (xN) kullandığı için ayrı CSV.
    st.download_button(
        "⬇️ Normal kuvvet verileri (CSV)",
        _diyagram_csv(["x [m]", "Normal [kN]"], result["xN"], result["N"]),
        file_name="diyagram_normal_kuvvet.csv",
        mime="text/csv",
    )

st.subheader("Mesnet tepkileri")
# Yatay tepki sütunu yalnız eksenel yük varken anlamlı (aksi halde tümü 0);
# moment tepkisi sütunu yalnız ankastre mesnet varken dolu — yoksa hep "—"
# olan gürültü sütunları gizlenir.
has_fixed = any(s == "fixed" for s in model.supports)
rows = []
for r in result["reactions"]:
    row = {
        "Düğüm": r["node"],
        "Konum [m]": round(r["x"], 3),
        "Düşey tepki [kN]": "—" if r["V"] is None else f"{r['V']:.3f}",
    }
    if has_axial:
        row["Yatay tepki [kN]"] = "—" if r["H"] is None else f"{r['H']:.3f}"
    if has_fixed:
        row["Moment tepkisi [kNm]"] = "—" if r["M"] is None else f"{r['M']:.3f}"
    rows.append(row)
# st.dataframe canvas tabanlı olduğu için gece modunda renklenmez; temalanabilir
# HTML tablo kullanılır (bkz. ui_tema.tepki_tablosu).
tepki_tablosu(rows)
