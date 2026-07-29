"""
PyCBA Web Arayüzü — Streamlit.

Yalnızca sunum katmanı: model kurulumu ve çözüm `core/` paketindedir.
Çalıştırma: .venv\\Scripts\\streamlit run app.py
"""

import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core import (
    AXIAL_KINDS, BeamModel, Load, LOAD_TYPES, SUPPORT_TYPES,
    check_load_position, solve, SolverError,
)
from ui_cizim import NORMAL_KUVVET_YESILI, ciz_sema
from ui_dil import DILLER, VARSAYILAN_DIL, cevir
from ui_tema import enjekte_tema, hero_baslik, tepki_tablosu

# Yük parametresi -> birim. Birimler dilden bağımsızdır (kN, m, kNm²); etiketler
# katalogdadır ("param.w" vb., bkz. ui_dil.py).
PARAM_UNITS = {
    "w": "kN/m", "w1": "kN/m", "w2": "kN/m", "P": "kN", "M": "kNm",
    "a": "m", "c": "m", "N": "kN", "n": "kN/m",
}

# Dil: kenar çubuğundaki seçim kutusu "dil"i yazar; tema modunda olduğu gibi
# burada (bir sonraki rerun'da) okunur. Widget aşağıda çizilir ama Streamlit her
# etkileşimde betiği baştan çalıştırdığı için seçim anında yansır.
dil = st.session_state.get("dil", VARSAYILAN_DIL)


def t(anahtar: str, **kw) -> str:
    """Seçili dilde arayüz metni (ui_dil.cevir'in bu oturuma bağlı hâli)."""
    return cevir(dil, anahtar, **kw)


st.set_page_config(page_title=t("sayfa_basligi"), page_icon="🏗️", layout="wide")
# Tema modu: kenar çubuğundaki toggle "tema_gece"yi yazar; burada (rerun'da)
# okunup CSS enjekte edilir. Toggle enjeksiyondan sonra çizilir ama Streamlit
# her etkileşimde baştan çalıştığı için değer bir sonraki rerun'da yansır.
mod = "gece" if st.session_state.get("tema_gece", False) else "aydinlik"
karanlik = mod == "gece"
enjekte_tema(mod)
hero_baslik(t("hero.baslik"), t("hero.altyazi"), t("hero.eyebrow"), t("sema.aria"))

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
    # KENAR ÇUBUĞUNDA `st.rerun()` ÇAĞIRMA — bunun yerine `yeniden_calistir`
    # bayrağını kur; blok sonunda bir kez çalıştırılır.
    # Neden: Streamlit, bir çalıştırmada ÇİZİLMEYEN widget'ın durumunu siler.
    # Ekleme/silme bloğunda hemen rerun edilince betik orada kesiliyor, o
    # bloktan SONRA gelen widget'lar (mesnet çökmesi alanları, "4. Görünüm"
    # anahtarları) hiç çizilmiyor ve durumları çöpe gidiyordu: kullanıcı sehim
    # grafiğini kapatıp yeni bir yük eklediğinde grafik varsayılanıyla geri
    # açılıyordu. Bayrağı blok sonunda tüketmek tüm kenar çubuğunun çizilmesini
    # garanti eder; ana alandaki (yük listesi) rerun'lar zaten kenar çubuğundan
    # sonra çalıştığı için doğrudan `st.rerun()` kullanmayı sürdürür.
    yeniden_calistir = False
    # Tema toggle: key "tema_gece" — üstte okunup CSS moduna karar verilir.
    st.toggle(t("gece_modu"), key="tema_gece")
    # Dil seçimi: key "dil" — üstte okunup `t()` bunun üzerinden kurulur.
    # Seçenek adları kendi dillerinde yazılır (bkz. ui_dil.DILLER).
    st.selectbox(
        t("dil_secimi"), list(DILLER), format_func=DILLER.get, key="dil",
    )

    st.header(t("bolum.geometri"))
    n_spans = st.number_input(t("aciklik_sayisi"), min_value=1, max_value=10, value=2)

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

    st.header(t("bolum.mesnetler"))
    supports = []
    for i in range(n_spans + 1):
        default = "pin" if i in (0, n_spans) else "roller"
        supports.append(
            st.selectbox(
                t("dugum_no", n=i + 1), SUPPORT_TYPES,
                index=SUPPORT_TYPES.index(default),
                format_func=lambda s: t(f"mesnet.{s}"),
                key=f"sup_{i}",
            )
        )

    # Gerber kirişi: ara düğümlere iç mafsal. Uç düğümlerde mafsal anlamsızdır
    # (orada tek eleman var; mesnet tipi zaten belirler), bu yüzden seçenekler
    # yalnız 2..n_spans. Anahtar açıklık sayısına bağlı — açıklık azalınca artık
    # var olmayan düğüm no'su seçili kalmasın.
    hinges = st.multiselect(
        t("mafsal.coklu_secim"),
        options=list(range(2, n_spans + 1)),
        format_func=lambda h: t("dugum_no", n=h),
        help=t("mafsal.yardim"),
        key=f"hinges_{n_spans}",
    )

    # Açıklık İÇİNDE mafsal: kullanıcı (açıklık, sol uçtan a) verir; core bunu
    # açıklığı bölüp araya mesnetsiz düğüm koyarak çözer (BeamModel.expand).
    # Kullanıcının açıklık ve yük numaralandırması değişmez.
    with st.expander(t("mafsal.baslik")):
        st.caption(t("mafsal.aciklama"))
        # Açıklık no form DIŞINDA (yük formuyla aynı desen ve aynı nedenle):
        # konum widget'ının key'i açıklık no'ya bağlı olduğundan, açıklık no form
        # İÇİNDE olsaydı gönderim anında key değişir, konum widget'ı yeniden kurulur
        # ve kullanıcının yazdığı değer sessizce 0'a düşerdi. Dışarıda olunca
        # açıklık değişimi anında rerun tetikler; hem a'nın max_value sınırı hem
        # de key, kullanıcı konumu yazmadan ÖNCE güncellenmiş olur.
        mh_span = int(st.number_input(
            t("mafsal.aciklik_no"), min_value=1, max_value=n_spans,
            value=1, step=1, key=f"mh_span_{n_spans}",
        ))
        L_mh = float(spans[mh_span - 1])
        with st.form("mafsal_ekle_form"):
            # Sayaç yük formundaki `add_nonce` ile aynı işi görür: mafsal eklenince
            # anahtar değişir, alan boş (placeholder "0") yeniden kurulur.
            mh_key = f"mh_a_{mh_span}_{L_mh:g}_{st.session_state.mh_nonce}"
            mh_a = st.number_input(
                t("mafsal.konum", L=L_mh),
                min_value=0.0, max_value=L_mh, value=None,
                step=0.25, placeholder="0", key=mh_key,
            )
            mh_ekle = st.form_submit_button(t("mafsal.ekle"), width="stretch")
        if mh_ekle:
            a_val = 0.0 if mh_a is None else float(mh_a)
            if not (0 < a_val < L_mh):
                st.error(t("mafsal.konum_hatasi", L=L_mh))
            elif (mh_span, a_val) in st.session_state.span_hinges:
                st.error(t("mafsal.zaten_var"))
            else:
                st.session_state.span_hinges.append((mh_span, a_val))
                st.session_state.pop(mh_key, None)
                st.session_state.mh_nonce += 1
                yeniden_calistir = True
        # Açıklık sayısı/uzunluğu küçültülünce geçersiz kalan mafsalları at —
        # yoksa model sürekli doğrulama hatası verip arayüzü kilitler.
        st.session_state.span_hinges = [
            (s, a) for s, a in st.session_state.span_hinges
            if 1 <= s <= n_spans and 0 < a < float(spans[s - 1])
        ]
        for j, (s, a) in enumerate(st.session_state.span_hinges):
            lc1, lc2 = st.columns([3, 1])
            lc1.write(t("mafsal.satir", sp=s, a=a))
            if lc2.button("🗑️", key=f"mh_sil_{j}"):
                # `break`: liste bu döngünün içinde kısaldı; kalan satırları
                # eski indekslerle çizmek yerine çık — blok sonundaki rerun
                # listeyi zaten güncel haliyle yeniden kuracak.
                st.session_state.span_hinges.pop(j)
                yeniden_calistir = True
                break

    # Mesnet çökmesi: mesnetli her düğüm için tek bir alan. Yük/mafsal
    # listelerindeki gibi ekle-sil kurgusu YOK — düğüm sayısı zaten sınırlı (≤11)
    # ve çökme bir düğümün TEK bir özelliğidir; alanın kendisi hem girdi hem
    # listedir, bayat anahtar/silme tuzağı doğmaz. Serbest düğümler listelenmez
    # (core doğrulaması da oraya çökme verilmesini reddeder).
    with st.expander(t("cokme.baslik")):
        st.caption(t("cokme.aciklama"))
        settlements = {}
        mesnetli = [i for i, s in enumerate(supports) if s != "free"]
        if not mesnetli:
            st.caption(t("cokme.mesnet_yok"))
        for i in mesnetli:
            cokme_mm = st.number_input(
                t("cokme.alan", n=i + 1), value=0.0, step=1.0, format="%.2f",
                help=t("cokme.yardim"), key=f"cokme_{i}",
            )
            if abs(cokme_mm) > 1e-12:
                # Arayüz mm ve "+ aşağı"; çekirdek m ve sehim `D` ile aynı işaret
                # (aşağı eksi) — birim ve işaret çevirisi burada, tek satırda.
                settlements[i + 1] = -float(cokme_mm) / 1000.0

    st.header(t("bolum.yukler"))
    # Önce hangi açıklığa yük konacağı, sonra yük tipi seçilir (doğal akış:
    # "nereye" → "ne"). Anahtar açıklık sayısına bağlı: kullanıcı açıklık sayısını
    # küçültünce eski (artık max_value dışında kalabilecek) değer taşınmaz — aksi
    # halde Streamlit "value > max_value" istisnası fırlatır. (a/c widget'larıyla
    # tutarlı "key'i bağla" deseni.)
    load_span = st.number_input(
        t("aciklik_no"), min_value=1, max_value=n_spans, value=1,
        key=f"load_span_{n_spans}",
    )
    L_sel = float(spans[load_span - 1])
    # Yük tipi adı core.LOAD_TYPES yerine katalogdan gelir (core dilsizdir);
    # anahtarlar aynı, önek "yuk." (bkz. ui_dil.py).
    kind = st.selectbox(
        t("yuk_tipi"), list(LOAD_TYPES), format_func=lambda k: t(f"yuk.{k}"),
    )
    st.caption(f'{t(f"ipucu.{kind}")}  {t("secili_aciklik", L=L_sel)}')
    # Parametreler bir form içinde toplanır: elle YAZILAN değerler (özellikle konum
    # a) ancak "Yük ekle"ye basınca topluca gönderilir. Form dışında number_input'a
    # yazılan değer widget odağı değişene kadar kaydedilmediğinden, yazıp butona
    # basınca eski (0) değer okunuyordu; +/- adımı ise anında commit ettiği için
    # çalışıyordu. Yük tipi ve açıklık no form DIŞINDA kaldı ki değişince a'nın
    # max_value=L sınırı ve parametre alanları anında yenilensin.
    with st.form("yuk_ekle_form"):
        values, param_keys = [], []
        for p in LOAD_TYPES[kind][2]:
            label, unit = t(f"param.{p}"), PARAM_UNITS[p]
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
        submitted = st.form_submit_button(t("yuk.ekle"), width="stretch")
    # Boş bırakılan (None) alanları 0.0 kabul et — doğrulama/çözüm float bekler.
    values = [0.0 if v is None else v for v in values]
    if submitted:
        # Şiddet parametreleri (konum a/c dışındakiler) tümü 0 ise yük eklemek
        # anlamsızdır; sessizce 0'lık yük eklemek yerine uyar.
        siddetler = [v for p, v in zip(LOAD_TYPES[kind][2], values) if p not in ("a", "c")]
        pos_err = check_load_position(kind, values, L_sel, dil)
        if all(abs(v) < 1e-12 for v in siddetler):
            st.error(t("yuk.siddet_sifir"))
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
            yeniden_calistir = True

    # -------------------------------------------------------------- görünüm
    # Hangi grafiklerin çizileceği. Kenar çubuğunda tutulur ki her durumda
    # (yük yokken, çözüm hata verirken de) erişilebilsin; ana alandaki çizim
    # bloklarının hepsi bu bayrakları okur.
    st.header(t("bolum.gorunum"))
    st.caption(t("gorunum.aciklama"))
    # Normal kuvvet grafiği yalnız eksenel yük varken anlamlı — yoksa toggle da
    # gösterilmez (kullanıcı boş bir anahtarla uğraşmasın).
    has_axial = any(ld.kind in AXIAL_KINDS for ld in st.session_state.loads)
    goster_sema = st.toggle(t("gorunum.sema"), value=True, key="goster_sema")
    goster_N = (
        st.toggle(t("gorunum.N"), value=True, key="goster_N")
        if has_axial else False
    )
    goster_V = st.toggle(t("gorunum.V"), value=True, key="goster_V")
    goster_M = st.toggle(t("gorunum.M"), value=True, key="goster_M")
    goster_D = st.toggle(t("gorunum.D"), value=True, key="goster_D")

    # Bayrak burada tüketilir: kenar çubuğunun TAMAMI çizildi, hiçbir widget'ın
    # durumu çöpe gitmez (bkz. bloğun başındaki not). Ana alan bu çalıştırmada
    # hiç hesaplanmaz — çözüm ve grafikler boşuna kurulmuş olmaz.
    if yeniden_calistir:
        st.rerun()

# --------------------------------------------------------------- yük listesi
st.subheader(t("liste.baslik"))
if not st.session_state.loads:
    st.info(t("liste.bos"))
else:
    st.caption(t("liste.duzenle_ipucu"))
    # Her yük açılır bir düzenleme formu: açıklık ve değerler değiştirilip
    # kaydedilebilir; hatalı girişte sil-ekle gerekmez. Yük tipini satır-içi
    # değiştirmiyoruz (nadir; bunun için silip yeniden ekleyin). Widget key'leri
    # yükün İÇERİĞİNE bağlı (indeks + span + değerler): bir yük silinip indeksler
    # kayınca veya kaydedince key değişir, alanlar güncel değerle yeniden kurulur;
    # düzenleme sırasında (kayıtlı içerik sabitken) key sabit kalıp yazılanı korur.
    for i, ld in enumerate(st.session_state.loads):
        _, _, params = LOAD_TYPES[ld.kind]
        desc = ", ".join(
            f"{p}={v:g} {PARAM_UNITS[p]}" for p, v in zip(params, ld.values)
        )
        sig = f"{i}_{ld.span}_" + "-".join(f"{v:g}" for v in ld.values)
        baslik = t("liste.satir", i=i + 1, ad=t(f"yuk.{ld.kind}"),
                   sp=ld.span, ayrinti=desc)
        with st.expander(baslik):
            # Açıklık seçimi form DIŞINDA (ekleme formundaki desenin aynısı).
            # Form İÇİNDE olduğunda değişiklik ancak gönderimde işleniyor, o
            # rerun'da konum widget'ı (key'i new_span'e bağlı) yeni açıklığa göre
            # sıfırdan kuruluyor ve kullanıcının aynı gönderimde yazdığı konum
            # sessizce yutuluyordu. Dışarıda değişiklik anında rerun tetikler:
            # konum alanları yeni L ile kurulur, sonra kaydedilir.
            #
            # Açıklık sayısı küçültülmüşse yükün açıklığı artık max_value'yu
            # aşıyor olabilir; Streamlit bu durumda istisna fırlatır ve kullanıcı
            # hata mesajı yerine traceback görür. Widget'ı sınıra çekiyoruz —
            # yük silinmiyor: model doğrulaması "açıklık no geçersiz" diye uyarır,
            # kullanıcı buradan düzeltip kaydeder ya da siler. (Mafsallarda aynı
            # durum satır 153'te temizlenir; yükte sessiz silme veri kaybı olurdu.)
            new_span = int(
                st.number_input(
                    t("aciklik_no"), min_value=1, max_value=n_spans,
                    value=min(ld.span, n_spans), step=1,
                    key=f"edit_span_{sig}",
                )
            )
            # Konum sınırı seçili açıklığın L'sine bağlı (ekleme formuyla aynı).
            L_edit = float(spans[new_span - 1])
            with st.form(f"duzenle_form_{sig}"):
                new_values = []
                for j, p in enumerate(params):
                    label, unit = t(f"param.{p}"), PARAM_UNITS[p]
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
                kaydet = bc1.form_submit_button(t("liste.kaydet"), width="stretch")
                sil = bc2.form_submit_button(t("liste.sil"), width="stretch")
            if sil:
                st.session_state.loads.pop(i)
                st.rerun()
            if kaydet:
                # Yeni açıklığın L'sine göre konum doğrula (açıklık değişmiş olabilir).
                pos_err = check_load_position(
                    ld.kind, new_values, float(spans[new_span - 1]), dil
                )
                siddetler = [
                    v for p, v in zip(params, new_values) if p not in ("a", "c")
                ]
                if all(abs(v) < 1e-12 for v in siddetler):
                    st.error(t("yuk.siddet_sifir_duzenle"))
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
    settlements=settlements,
)

errors = model.validate(dil)
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
    st.subheader(t("sema.baslik"))
    fig_schema, ax_schema = plt.subplots(figsize=(10, yukseklik))
    ciz_sema(ax_schema, model, reactions, dil)
    st.pyplot(fig_schema, width="stretch")
    plt.close(fig_schema)


# Yük ve çökme yoksa çözüm (dolayısıyla tepki) yok: yalnızca şemayı çiz ve dur.
# Çökme tek başına da sonuç üretir (hiperstatikte kesit tesiri, her durumda
# sehim), bu yüzden "yük yok" koşuluna takılmamalı.
if not st.session_state.loads and not settlements:
    _sema_ciz()
    st.info(t("sonuclar.yuk_ekleyin"))
    st.stop()

# Yük var: tepki oklarını çizebilmek için önce çöz. Çözülemezse şemayı yine de
# yükleriyle göster ve hatayı bildir.
try:
    result = solve(model, dil)
except SolverError as e:
    _sema_ciz()
    st.error(str(e))
    st.stop()

# Şema + mesnet tepki okları (oklar/etiketler için biraz daha yüksek figür).
_sema_ciz(result["reactions"], yukseklik=3.4)

# ------------------------------------------------------------------ sonuçlar
st.subheader(t("sonuclar.baslik"))

# Eksenel çözücü EA=1 varsayar; bu yalnız eksenel sistem hiperstatikken VE
# açıklıkların kesiti farklıyken yatay tepki paylaşımını etkiler (bkz.
# core/axial.py). Çekirdek bunu bayrakla bildirir, sunum katmanı gösterir.
if result["ea_uyari"]:
    st.warning(t("uyari.ea"))

# İzostatik sistemde çökme yalnız rijit yer değiştirme üretir; M ve V sıfır
# çıkar. Bu doğru davranıştır ama "hesap çalışmadı" gibi okunur — nedeni söyle.
if settlements and model.static_degree() == 0:
    st.info(t("uyari.cokme_izostatik"))

# (has_axial kenar çubuğunda "4. Görünüm" için zaten hesaplandı.)
# Metrik kartları görünüm toggle'larından etkilenmez: sayısal özet kompakttır ve
# grafiği kapatan kullanıcı da ekstrem değerleri görmek ister.

# Her büyüklükte işaretli maks + min gösterilir (yalnız mutlak değil): negatif
# ekstremler mühendislik açısından da anlamlıdır (örn. mesnet üstü negatif
# moment). Büyük rakam mutlak değerce YÖNETEN ekstremdir, işaretiyle; diğeri
# caption'da kalır. Caption ayrıca ekstremlerin kiriş üzerindeki konumunu (x)
# verir — argmax/argmin saf sunum hesabı, core değişmez.
def _ekstrem_konum(x_arr, y_arr, en_buyuk):
    """Ekstremin (maks/min) apsis konumunu [m] döndür."""
    idx = int(y_arr.argmax() if en_buyuk else y_arr.argmin())
    return float(x_arr[idx])

def _biciml(v, olcek=1.0):
    """Ekstremi karta yazılacak metne çevir; "-0.00"ı "0.00" yapar.

    Sıfır diyagram parçalarında kayan nokta -0.0 veya -1e-16 üretir; ikisi de
    "-0.00" diye basılır ve okuyan basınç sanır. Gösterim hassasiyetine
    yuvarlayıp +0.0 eklemek negatif sıfırı pozitife çevirir.
    """
    return f"{round(v * olcek, 2) + 0.0:.2f}"

def _kart(col, buyukluk, birim, xd, yd, olcek=1.0):
    """Kartı çiz: büyük rakam mutlak değerce yöneten ekstrem, diğeri caption'da.

    Önceden büyük rakam HER ZAMAN maks'tı; basit kirişte sehim maksimumu 0.00
    olduğu için kart "Maks. sehim 0.00" yazıyor, asıl −11.25 mm küçük caption'a
    düşüyordu (kesmede de 52.50 gösterilip yöneten 67.50 alta iniyordu). Kesit
    tahkikinde yöneten mutlak değerce büyük olandır; başlık hangi ekstremin
    gösterildiğini söyler ("Maks." / "Min.").
    """
    vmaks, vmin = float(yd.max()), float(yd.min())
    x_maks, x_min = _ekstrem_konum(xd, yd, True), _ekstrem_konum(xd, yd, False)
    if abs(vmaks) >= abs(vmin):
        baslik, deger, x_dom = "kart.maks", vmaks, x_maks
        alt, alt_deger, x_alt = "kart.min", vmin, x_min
    else:
        baslik, deger, x_dom = "kart.min_baslik", vmin, x_min
        alt, alt_deger, x_alt = "kart.maks_alt", vmaks, x_maks
    col.metric(t(baslik, ad=t(f"buyukluk.{buyukluk}"), birim=birim),
               _biciml(deger, olcek))
    col.caption(
        t("kart.konum", x=x_dom) + "  \n"
        + t(alt, deger=_biciml(alt_deger, olcek), x=x_alt)
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
        (t("panel.normal"), "kN", result["xN"], result["N"],
         NORMAL_KUVVET_YESILI, "rgba(44,160,44,0.15)", False)
    )
# (ad, birim, x, y, çizgi_rengi, dolgu_rgba|None, y_ekseni_ters)
if goster_V:
    paneller.append(
        (t("panel.kesme"), "kN", result["x"], result["V"],
         _KIRMIZI, _KIRMIZI_DOLGU, False)
    )
if goster_M:
    paneller.append(
        (t("panel.moment"), "kNm", result["x"], result["M"],
         _KIRMIZI, _KIRMIZI_DOLGU, True)
    )
if goster_D:
    paneller.append(
        (t("panel.sehim"), "mm", result["x"], result["D"] * 1000.0,
         _KIRMIZI, None, False)
    )
n_panel = len(paneller)
if n_panel == 0:
    # Hepsi kapalı: boş figür çizmek yerine nereden açılacağını söyle.
    st.info(t("diyagram.hepsi_kapali"))
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

    # --- Mesnet çizgileri: diyagramı kirişle hizalar -------------------------
    # Harfler ŞEMAYLA aynı kuralla üretilir (bkz. ui_cizim.ciz_sema): "free"
    # düğümler atlanır, çizilen mesnetler sıfırdan sırayla harflenir. İki görsel
    # farklı harf gösterirse tepki tablosuyla eşleştirme bozulur.
    # Izgaradan belirgin, kiriş çizgisinden silik: yapı ipucu, veri değil.
    _g_mesnet = "rgba(255,255,255,0.22)" if karanlik else "rgba(28,27,25,0.18)"
    _node_x = np.concatenate([[0.0], np.cumsum(model.spans)])
    for sira, (idx_node, _tip) in enumerate(
        (j, s) for j, s in enumerate(model.supports) if s != "free"
    ):
        x_m = float(_node_x[idx_node])
        fig.add_vline(x=x_m, line=dict(color=_g_mesnet, width=1, dash="dot"),
                      row="all", col=1)
        fig.add_annotation(
            x=x_m, y=1.0, yref="y domain", yanchor="bottom", yshift=2,
            text=chr(ord("A") + sira), showarrow=False,
            font=dict(color=_g_yazi, size=11), row=1, col=1,
        )

    # --- Ekstrem işaretleri --------------------------------------------------
    # Metrik kartları ekstrem DEĞERİ veriyor ama konumunu vermiyor; işaretçi
    # "nerede" sorusunu cevaplar. Konum dizilerden okunur — tümü sunum işi,
    # core dokunulmaz.
    _g_halka = "#1E2028" if karanlik else "#FFFFFF"
    for i, (ad, birim, xr, yr, renk, _dolgu, ters) in enumerate(paneller, start=1):
        olcek = float(np.max(np.abs(yr)))
        if olcek < 1e-9:  # düz sıfır diyagram: işaretlenecek uç yok
            continue
        boy = float(xr[-1]) or 1.0
        gorulen = set()
        for idx, ust in ((int(np.argmax(yr)), True), (int(np.argmin(yr)), False)):
            deger = float(yr[idx])
            # Tek işaretli diyagramlarda "diğer" uç sıfırdadır ve bilgi taşımaz;
            # aynı nokta iki kez de işaretlenmemeli (sabit diyagram).
            if idx in gorulen or abs(deger) < 0.02 * olcek:
                continue
            gorulen.add(idx)
            x_e = float(xr[idx])
            fig.add_trace(
                go.Scatter(
                    x=[x_e], y=[deger], mode="markers", showlegend=False,
                    marker=dict(color=renk, size=8,
                                line=dict(color=_g_halka, width=1.6)),
                    hoverinfo="skip",  # eğrinin kendi ipucu yeter, ikilenmesin
                ),
                row=i, col=1,
            )
            fig.add_annotation(
                x=x_e, y=deger, text=f"{deger:.4g} {birim} · {x_e:.2f} m",
                showarrow=False,
                # yshift EKRAN pikselidir: moment panelinde y ekseni ters olduğu
                # için veri uzayındaki "üst" ekranda alta düşer, yön de terslenir.
                yshift=(16 if ust else -16) * (-1 if ters else 1),
                # Uçlardaki etiket panel dışına taşıp kırpılmasın diye yaslanır.
                xanchor="left" if x_e < 0.12 * boy else
                        ("right" if x_e > 0.88 * boy else "center"),
                font=dict(color=_g_yazi, size=10),
                bgcolor=_g_halka, borderpad=2, opacity=0.92,
                row=i, col=1,
            )

    fig.update_xaxes(title_text=t("diyagram.eksen_x"), row=n_panel, col=1)
    # fixedrange=True: dokunmatik ekranda grafik zoom/pan/pinch yapmaz — parmak
    # hareketi sayfayı kaydırır, grafiği değil. Hover ipuçları çalışmaya devam eder.
    # tickfont/title_font AÇIKÇA verilir: Streamlit'in plotly şablonu eksen
    # yazılarını rgb(128,132,149) yapar ve layout `font=` bunu EZMEZ — ölçülen
    # kontrast her iki modda da AA altında (≈3.8:1 / 4.2:1) kalıyordu.
    _eksen_yazi = dict(tickfont=dict(color=_g_yazi), title_font=dict(color=_g_yazi))
    fig.update_xaxes(gridcolor=_g_izgara, zerolinecolor=_g_sifir, linecolor=_g_izgara,
                     fixedrange=True, **_eksen_yazi)
    fig.update_yaxes(gridcolor=_g_izgara, zerolinecolor=_g_sifir, fixedrange=True,
                     **_eksen_yazi)
    fig.update_layout(
        # Başlık rengi açıkça verilir; aksi halde Streamlit'in plotly şablonu koyu
        # bırakıp gece modunda okunmaz kılıyordu.
        title=dict(text=t("diyagram.baslik"), y=0.99, yanchor="top",
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
    t("csv.diyagram_buton"),
    _diyagram_csv(
        [t("csv.x"), t("csv.moment"), t("csv.kesme"), t("csv.sehim")],
        result["x"], result["M"], result["V"], result["D"] * 1000.0,
    ),
    file_name=t("csv.diyagram_dosya"),
    mime="text/csv",
)
if has_axial:
    # N kendi apsis dizisini (xN) kullandığı için ayrı CSV.
    st.download_button(
        t("csv.normal_buton"),
        _diyagram_csv([t("csv.x"), t("csv.normal")], result["xN"], result["N"]),
        file_name=t("csv.normal_dosya"),
        mime="text/csv",
    )

st.subheader(t("tepki.baslik"))
# Yatay tepki sütunu yalnız eksenel yük varken anlamlı (aksi halde tümü 0);
# moment tepkisi sütunu yalnız ankastre mesnet varken dolu — yoksa hep "—"
# olan gürültü sütunları gizlenir.
has_fixed = any(s == "fixed" for s in model.supports)
rows = []
for r in result["reactions"]:
    row = {
        t("tepki.dugum"): r["node"],
        t("tepki.konum"): round(r["x"], 3),
        t("tepki.dusey"): "—" if r["V"] is None else f"{r['V']:.3f}",
    }
    if has_axial:
        row[t("tepki.yatay")] = "—" if r["H"] is None else f"{r['H']:.3f}"
    if has_fixed:
        row[t("tepki.moment")] = "—" if r["M"] is None else f"{r['M']:.3f}"
    rows.append(row)
# st.dataframe canvas tabanlı olduğu için gece modunda renklenmez; temalanabilir
# HTML tablo kullanılır (bkz. ui_tema.tepki_tablosu).
tepki_tablosu(rows)
