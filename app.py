"""
PyCBA Web Arayüzü — Streamlit.

Yalnızca sunum katmanı: model kurulumu ve çözüm `core/` paketindedir.
Çalıştırma: .venv\\Scripts\\streamlit run app.py
"""

import matplotlib.pyplot as plt
import plotly.graph_objects as go
import streamlit as st

from core import (
    AXIAL_KINDS, BeamModel, Load, LOAD_TYPES, SUPPORT_TYPES,
    check_load_position, solve, SolverError,
)
from ui_cizim import NORMAL_KUVVET_YESILI, ciz_sema

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
st.title("🏗️ Sürekli Kiriş Analizi — PyCBA")

if "loads" not in st.session_state:
    st.session_state.loads = []  # list[Load]

# ---------------------------------------------------------------- girdi paneli
with st.sidebar:
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

    st.header("3. Yükler")
    kind = st.selectbox(
        "Yük tipi", list(LOAD_TYPES), format_func=lambda k: LOAD_TYPES[k][1],
    )
    # Anahtar açıklık sayısına bağlı: kullanıcı açıklık sayısını küçültünce
    # eski (artık max_value dışında kalabilecek) değer taşınmaz — aksi halde
    # Streamlit "value > max_value" istisnası fırlatır. (a/c widget'larıyla
    # tutarlı "key'i bağla" deseni.)
    load_span = st.number_input(
        "Açıklık no", min_value=1, max_value=n_spans, value=1,
        key=f"load_span_{n_spans}",
    )
    L_sel = float(spans[load_span - 1])
    st.caption(f"{KIND_HINTS[kind]}  (Seçili açıklık: L = {L_sel:g} m)")
    # Parametreler bir form içinde toplanır: elle YAZILAN değerler (özellikle konum
    # a) ancak "Yük ekle"ye basınca topluca gönderilir. Form dışında number_input'a
    # yazılan değer widget odağı değişene kadar kaydedilmediğinden, yazıp butona
    # basınca eski (0) değer okunuyordu; +/- adımı ise anında commit ettiği için
    # çalışıyordu. Yük tipi ve açıklık no form DIŞINDA kaldı ki değişince a'nın
    # max_value=L sınırı ve parametre alanları anında yenilensin.
    with st.form("yuk_ekle_form"):
        values = []
        for p in LOAD_TYPES[kind][2]:
            label, unit = PARAM_LABELS[p]
            if p in ("a", "c"):
                # Konum parametreleri açıklık uzunluğunu aşamaz. Anahtar açıklığa ve
                # L'ye bağlı: açıklık/uzunluk değişince eski (artık geçersiz olabilecek)
                # değer taşınmaz.
                kw = dict(min_value=0.0, max_value=L_sel, step=0.25)
                key = f"lv_{kind}_{p}_{load_span}_{L_sel:g}"
            else:
                kw = dict(step=1.0)
                key = f"lv_{kind}_{p}"
            values.append(st.number_input(f"{label} [{unit}]", value=0.0, key=key, **kw))
        submitted = st.form_submit_button("➕ Yük ekle", width="stretch")
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
            st.rerun()

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
model = BeamModel(spans=spans, EI=EI, supports=supports, loads=st.session_state.loads)

errors = model.validate()
if errors:
    for e in errors:
        st.error(e)
    st.stop()

# Kiriş şeması: mesnetler + yükler konumlarıyla çizilir, model her değiştiğinde
# güncellenir — kullanıcı yükü nereye etki ettirdiğini burada görür. Çözüm
# yapılabiliyorsa mesnet tepkileri de ok olarak şemanın üzerine eklenir.
st.subheader("Kiriş şeması")

# Yük yoksa çözüm (dolayısıyla tepki) yok: yalnızca şemayı çiz ve dur.
if not st.session_state.loads:
    fig_schema, ax_schema = plt.subplots(figsize=(10, 2.6))
    ciz_sema(ax_schema, model)
    st.pyplot(fig_schema, width="stretch")
    plt.close(fig_schema)
    st.info("Sonuçlar ve mesnet tepkileri için en az bir yük ekleyin.")
    st.stop()

# Yük var: tepki oklarını çizebilmek için önce çöz. Çözülemezse şemayı yine de
# yükleriyle göster ve hatayı bildir.
try:
    result = solve(model)
except SolverError as e:
    fig_schema, ax_schema = plt.subplots(figsize=(10, 2.6))
    ciz_sema(ax_schema, model)
    st.pyplot(fig_schema, width="stretch")
    plt.close(fig_schema)
    st.error(str(e))
    st.stop()

# Şema + mesnet tepki okları (oklar/etiketler için biraz daha yüksek figür).
fig_schema, ax_schema = plt.subplots(figsize=(10, 3.4))
ciz_sema(ax_schema, model, result["reactions"])
st.pyplot(fig_schema, width="stretch")
plt.close(fig_schema)

# ------------------------------------------------------------------ sonuçlar
st.subheader("Sonuçlar")

# Eksenel yük varsa normal kuvvet metriği ve diyagramı da gösterilir.
has_axial = any(ld.kind in AXIAL_KINDS for ld in st.session_state.loads)

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

fig = result["analysis"].plot_results(backend="plotly")
# Streamlit teması boş (None) başlığı "undefined" olarak çizer; açık başlık ver.
# PyCBA figürü başlıksız düzen için t=20 bırakır; başlık için üst boşluğu aç.
fig.update_layout(
    title=dict(text="Moment · Kesme · Sehim Diyagramları", y=0.99, yanchor="top"),
    margin=dict(t=70),
    height=750,  # 3 panel basık kalmasın; eksen başlıkları çakışmasın
)
# PyCBA eksen/iz adları İngilizce üretir; sunum katmanında Türkçeleştir.
# Panel sırası plot_results ile sabit: 1=moment, 2=kesme, 3=sehim.
_panel_tr = [("Moment", "kNm"), ("Kesme", "kN"), ("Sehim", "mm")]
for row, (ad, birim) in enumerate(_panel_tr, start=1):
    fig.update_yaxes(title_text=f"{ad} [{birim}]", row=row, col=1)
    if row - 1 < len(fig.data):
        tr = fig.data[row - 1]
        tr.name = ad
        tr.hovertemplate = f"{ad}: %{{y:.4g}} {birim}<extra></extra>"
fig.update_xaxes(title_text="Kiriş boyunca konum [m]", row=3, col=1)
st.plotly_chart(fig, width="stretch")
st.download_button(
    "⬇️ Diyagram verileri (CSV)",
    _diyagram_csv(
        ["x [m]", "Moment [kNm]", "Kesme [kN]", "Sehim [mm]"],
        result["x"], result["M"], result["V"], result["D"] * 1000.0,
    ),
    file_name="diyagram_moment_kesme_sehim.csv",
    mime="text/csv",
)

# Normal kuvvet diyagramı: PyCBA plot_results eksenel çözmez; core/axial.py
# sonucu (xN çift-nokta dizisi, süreksizlikler keskin) ayrı Plotly grafiğiyle
# çizilir. Yalnızca eksenel yük tanımlıysa gösterilir.
if has_axial:
    # Şema ile ortak yeşil (ui_cizim.NORMAL_KUVVET_YESILI); doygun blok yerine
    # ince çizgi + düşük opaklık dolgu — status (iyi/kötü) çağrışımından uzak,
    # süreksizlikler daha okunur.
    fig_n = go.Figure(
        go.Scatter(
            x=result["xN"], y=result["N"],
            mode="lines", fill="tozeroy", name="Normal kuvvet",
            line=dict(color=NORMAL_KUVVET_YESILI, width=1.5),
            fillcolor="rgba(44,160,44,0.15)",
            hovertemplate="Normal: %{y:.4g} kN<extra></extra>",
        )
    )
    fig_n.update_layout(
        title=dict(text="Normal Kuvvet Diyagramı (çekme +)", y=0.95, yanchor="top"),
        height=320,
        margin=dict(t=60, b=40),
        xaxis_title="Kiriş boyunca konum [m]",
        yaxis_title="Normal kuvvet [kN]",
        showlegend=False,
    )
    st.plotly_chart(fig_n, width="stretch")
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
st.dataframe(rows, width="stretch", hide_index=True)
