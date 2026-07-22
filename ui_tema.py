"""
Arayüz teması — sunum katmanı (yalnız Streamlit için).

CSS enjeksiyonuyla yazı tipi, renk, kart, hover, giriş animasyonları, aydınlık/
gece modu ve mobil uyarlamayı uygular; hesap mantığıyla ilgisi yoktur (core'a
hiç dokunmaz). Temeller: Emil Kowalski animasyon mühendisliği (özel easing,
kısa süreler, scale(.98) press-feedback, yalnız transform/opacity, reduced-
motion) + minimalist-ui (sıcak monokrom yüzey, 1px kenarlık, ince gölge, indigo
aksan).

Tema modeli: Streamlit temayı Emotion (CSS-in-JS) ile runtime'da uygular ve
kararlı CSS değişkeni sunmaz; bu yüzden gece modu tamamen burada, kendi CSS
değişkenlerimizle (`--pc-*`) yönetilir. Değerler moda göre değişir; yapısal CSS
sabittir ve bu değişkenleri kullanır. Grafikler/şema her iki modda okunur kalır
(plotly şeffaf + app.py moda göre renklendirir; matplotlib şema beyaz "kağıt").

Giriş (fade-up) animasyonu yalnız oturumun ilk yüklemesinde oynatılır.
"""

import streamlit as st

# --- Moda göre CSS değişkenleri --------------------------------------------
_VARS = {
    "aydinlik": {
        "bg": "#FBFBFA", "surface": "#FFFFFF", "surface2": "#F3F2EF",
        "ink": "#1C1B19", "muted": "#6F6B64", "line": "rgba(28,27,25,0.10)",
        "acc": "#4338CA", "acc2": "#6366F1",
    },
    "gece": {
        "bg": "#15161B", "surface": "#1E2028", "surface2": "#262933",
        "ink": "#E9E7E2", "muted": "#9C988F", "line": "rgba(255,255,255,0.12)",
        "acc": "#818CF8", "acc2": "#A5B4FC",
    },
}


def _degiskenler(mod: str) -> str:
    v = _VARS.get(mod, _VARS["aydinlik"])
    return (
        "<style>:root{"
        f"--pc-bg:{v['bg']};--pc-surface:{v['surface']};--pc-surface2:{v['surface2']};"
        f"--pc-ink:{v['ink']};--pc-muted:{v['muted']};--pc-line:{v['line']};"
        f"--pc-acc:{v['acc']};--pc-acc2:{v['acc2']};"
        "--pc-r:14px;--pc-r-sm:10px;"
        "--pc-ease:cubic-bezier(0.23,1,0.32,1);"
        "--pc-sh-sm:0 1px 2px rgba(0,0,0,0.06);"
        "--pc-sh-md:0 10px 26px -10px rgba(0,0,0,0.28);"
        "}</style>"
    )


# --- Her zaman: yapısal tema (değişkenleri kullanır, moda göre uyarlanır) ----
_TEMA_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');

/* Ambient arkaplan — çok düşük opaklık, derinlik */
[data-testid="stAppViewContainer"] {
  background-image:
    radial-gradient(1100px 520px at 100% -8%, rgba(99,102,241,0.07), transparent 60%),
    radial-gradient(820px 460px at -6% 4%, rgba(129,140,248,0.05), transparent 55%);
}

/* Görüntü (display) yazı tipi */
h1, h2, h3, [data-testid="stMetricValue"],
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button,
.pc-hero__title, .pc-hero__eyebrow {
  font-family: 'Space Grotesk', ui-sans-serif, system-ui, -apple-system, sans-serif !important;
  letter-spacing: -0.018em;
}

/* --- Hero başlık --- */
.pc-hero { margin: 0.2rem 0 1.3rem; padding-bottom: 1.1rem; border-bottom: 1px solid var(--pc-line); }
.pc-hero__eyebrow {
  display: inline-flex; align-items: center; gap: 0.6ch; font-size: 0.72rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.16em; color: var(--pc-acc); margin-bottom: 0.55rem;
}
.pc-hero__eyebrow::before {
  content: ""; width: 22px; height: 2px; border-radius: 2px;
  background: linear-gradient(90deg, var(--pc-acc), var(--pc-acc2));
}
.pc-hero__title {
  margin: 0; font-weight: 600; line-height: 1.03; font-size: clamp(1.7rem, 3.6vw, 3rem);
  background: linear-gradient(96deg, var(--pc-ink) 34%, var(--pc-acc) 118%);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent; color: transparent;
}
.pc-hero__sub { margin: 0.5rem 0 0; color: var(--pc-muted); font-size: 1.02rem; max-width: 64ch; }
.pc-hero__line {
  margin-top: 0.9rem; height: 3px; width: 84px; border-radius: 3px; transform-origin: left center;
  background: linear-gradient(90deg, var(--pc-acc), var(--pc-acc2));
}

/* --- Bölüm başlıkları — aksan çubuğu --- */
[data-testid="stMainBlockContainer"] h3 { position: relative; padding-left: 0.8rem; font-weight: 600; }
[data-testid="stMainBlockContainer"] h3::before {
  content: ""; position: absolute; left: 0; top: 0.16em; bottom: 0.16em; width: 4px; border-radius: 3px;
  background: linear-gradient(180deg, var(--pc-acc), var(--pc-acc2));
}

/* --- Metrik kartları --- */
[data-testid="stMetric"] {
  background: var(--pc-surface); border: 1px solid var(--pc-line); border-radius: var(--pc-r);
  padding: 1rem 1.1rem 0.9rem; box-shadow: var(--pc-sh-sm); position: relative; overflow: hidden;
  transition: transform 200ms var(--pc-ease), box-shadow 220ms var(--pc-ease), border-color 220ms var(--pc-ease);
}
[data-testid="stMetric"]::before {
  content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, var(--pc-acc), var(--pc-acc2));
}
[data-testid="stMetricValue"] { font-weight: 600; font-size: 1.6rem; color: var(--pc-ink) !important; }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * { color: var(--pc-muted) !important; font-weight: 500; }
@media (hover: hover) and (pointer: fine) {
  [data-testid="stMetric"]:hover { transform: translateY(-3px); box-shadow: var(--pc-sh-md); border-color: var(--pc-acc); }
}

/* --- Butonlar: press feedback + hover --- */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
  border-radius: 10px; font-weight: 600;
  transition: transform 140ms var(--pc-ease), box-shadow 160ms var(--pc-ease),
              border-color 160ms var(--pc-ease), background-color 160ms var(--pc-ease);
}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
  border-color: var(--pc-acc); box-shadow: var(--pc-sh-sm);
}
.stButton > button:active, .stDownloadButton > button:active, [data-testid="stFormSubmitButton"] > button:active {
  transform: scale(0.98);
}

/* --- Genişleyen yük kartları --- */
[data-testid="stExpander"] details {
  border: 1px solid var(--pc-line) !important; border-radius: var(--pc-r-sm) !important; overflow: hidden;
  box-shadow: var(--pc-sh-sm);
  transition: box-shadow 220ms var(--pc-ease), border-color 220ms var(--pc-ease);
}
[data-testid="stExpander"] details:hover { border-color: var(--pc-acc) !important; box-shadow: var(--pc-sh-md); }
[data-testid="stExpander"] summary { font-weight: 500; }
[data-testid="stExpander"] summary:hover { color: var(--pc-acc); }

/* --- Grafik kartı (plotly şeffaf; kart yüzeyi moda göre) --- */
[data-testid="stPlotlyChart"] {
  border: 1px solid var(--pc-line); border-radius: var(--pc-r); padding: 10px 6px;
  background: var(--pc-surface); box-shadow: var(--pc-sh-sm);
}

/* --- Girdi odak halkası (Streamlit 1.59: baseweb sarmalayıcı yerine testid) --- */
[data-testid="stNumberInputContainer"]:focus-within,
[data-testid="stSelectbox"] div:has(> input):focus-within {
  border-color: var(--pc-acc) !important; box-shadow: 0 0 0 3px color-mix(in srgb, var(--pc-acc) 22%, transparent) !important;
}

/* --- Kenar çubuğu --- */
[data-testid="stSidebar"] { border-right: 1px solid var(--pc-line); }
[data-testid="stSidebar"] h2 {
  font-size: 1.0rem; letter-spacing: -0.01em; padding-bottom: 0.35rem; margin-bottom: 0.2rem;
  border-bottom: 1px solid var(--pc-line);
}

/* --- Uyarılar --- */
[data-testid="stAlert"] { border-radius: var(--pc-r-sm); }

/* --- Tepki tablosu (HTML — her iki modda temalanır) --- */
.pc-tablo-wrap { overflow-x: auto; border: 1px solid var(--pc-line); border-radius: var(--pc-r-sm); box-shadow: var(--pc-sh-sm); }
.pc-tablo { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
.pc-tablo th, .pc-tablo td { padding: 0.55rem 0.85rem; text-align: right; white-space: nowrap; border-bottom: 1px solid var(--pc-line); }
.pc-tablo th:first-child, .pc-tablo td:first-child { text-align: left; }
.pc-tablo thead th {
  background: var(--pc-surface2); color: var(--pc-muted); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.04em; font-size: 0.74rem; position: sticky; top: 0;
}
.pc-tablo tbody tr { background: var(--pc-surface); color: var(--pc-ink); transition: background-color 160ms var(--pc-ease); }
.pc-tablo tbody tr:hover { background: color-mix(in srgb, var(--pc-acc) 8%, var(--pc-surface)); }
.pc-tablo tbody tr:last-child td { border-bottom: none; }

/* --- Mobil uyarlama --- */
@media (max-width: 640px) {
  .pc-hero__title { font-size: 1.55rem; }
  .pc-hero__sub { font-size: 0.92rem; }
  [data-testid="stMainBlockContainer"] { padding-left: 0.8rem !important; padding-right: 0.8rem !important; }
  [data-testid="stMetric"] { padding: 0.75rem 0.85rem; }
  [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
  [data-testid="stPlotlyChart"] { padding: 6px 2px; }
  .pc-tablo { font-size: 0.82rem; }
  .pc-tablo th, .pc-tablo td { padding: 0.45rem 0.6rem; }
  /* Metrik/kolon satırları dar ekranda sarsın (4 kart tek sırada ezilmesin) */
  [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex: 1 1 44% !important; min-width: 44% !important; }
}

/* --- Azaltılmış hareket --- */
@media (prefers-reduced-motion: reduce) {
  [data-testid="stMainBlockContainer"], .pc-hero__line, [data-testid="stSidebar"] { animation: none !important; }
  [data-testid="stMetric"], .stButton > button, .stDownloadButton > button,
  [data-testid="stFormSubmitButton"] > button, [data-testid="stExpander"] details, .pc-tablo tbody tr { transition: none !important; }
  [data-testid="stMetric"]:hover { transform: none !important; }
}
</style>"""


# --- Yalnız gece modu: Streamlit'in kendi yüzey/metin/widget renkleri --------
# (Streamlit teması config'de light; gece modunda bu yüzeyleri CSS ile bastırırız.
# Yalnız bu uygulamada kullanılan widget'lar hedeflenir.)
_GECE_CSS = """<style>
[data-testid="stApp"], [data-testid="stAppViewContainer"], .main, [data-testid="stBottomBlockContainer"] {
  background-color: var(--pc-bg) !important;
}
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stSidebar"] { background-color: var(--pc-surface2) !important; }
/* Genel metin */
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li,
[data-testid="stMainBlockContainer"] h1, [data-testid="stMainBlockContainer"] h2, [data-testid="stMainBlockContainer"] h3,
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
label, [data-testid="stWidgetLabel"] *, [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {
  color: var(--pc-ink) !important;
}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color: var(--pc-muted) !important; }
/* Girdi & select yüzeyleri — Streamlit 1.59'da number_input artık
   [data-baseweb="input"] sarmalayıcısı kullanmıyor; kontrol yüzeyi testid'lerle
   (ve select'te "input içeren div" ile) hedeflenir, yoksa gece modunda beyaz kalır. */
[data-testid="stNumberInputContainer"],
[data-testid="stSelectbox"] div:has(> input),
[data-baseweb="textarea"], [data-baseweb="textarea"] textarea {
  background-color: var(--pc-surface2) !important; border-color: var(--pc-line) !important;
}
[data-testid="stNumberInputField"], [data-baseweb="textarea"] textarea,
[data-testid="stSelectbox"] div:has(> input), [data-testid="stSelectbox"] input {
  color: var(--pc-ink) !important;
}
[data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"] {
  background-color: var(--pc-surface) !important; color: var(--pc-ink) !important;
}
/* İkincil butonlar / indirme / form gönder (secondary) */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button[kind="secondary"] {
  background-color: var(--pc-surface) !important; color: var(--pc-ink) !important; border-color: var(--pc-line) !important;
}
/* Form ve genişleyen yüzeyi */
[data-testid="stForm"] { background-color: var(--pc-surface) !important; border-color: var(--pc-line) !important; }
[data-testid="stExpander"] details { background-color: var(--pc-surface) !important; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: var(--pc-ink) !important; }
</style>"""


# --- Yalnız ilk yüklemede: giriş (fade-up) animasyonu -----------------------
_GIRIS_CSS = """<style>
@keyframes pcFadeUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
@keyframes pcGrow  { from { transform: scaleX(0); } to { transform: scaleX(1); } }
[data-testid="stMainBlockContainer"] { animation: pcFadeUp 560ms var(--pc-ease) both; }
[data-testid="stSidebar"] { animation: pcFadeUp 560ms var(--pc-ease) both; }
.pc-hero__line { animation: pcGrow 720ms var(--pc-ease) 140ms both; }
</style>"""


def enjekte_tema(mod: str = "aydinlik"):
    """Moda göre değişkenleri + yapısal temayı enjekte et; gece modunda Streamlit
    yüzeylerini bastır; giriş animasyonunu yalnız ilk yüklemede oynat."""
    ilk = not st.session_state.get("_tema_giris_oynatildi", False)
    st.session_state["_tema_giris_oynatildi"] = True
    st.markdown(_degiskenler(mod), unsafe_allow_html=True)
    st.markdown(_TEMA_CSS, unsafe_allow_html=True)
    if mod == "gece":
        st.markdown(_GECE_CSS, unsafe_allow_html=True)
    if ilk:
        st.markdown(_GIRIS_CSS, unsafe_allow_html=True)


def hero_baslik(baslik: str, altyazi: str, eyebrow: str = "Yapı statiği · sürekli kiriş"):
    """st.title yerine animasyonlu, gradyan-aksanlı hero başlık bloğu çiz."""
    st.markdown(
        f'<div class="pc-hero">'
        f'<div class="pc-hero__eyebrow">{eyebrow}</div>'
        f'<h1 class="pc-hero__title">{baslik}</h1>'
        f'<p class="pc-hero__sub">{altyazi}</p>'
        f'<div class="pc-hero__line"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def tepki_tablosu(rows: list[dict]):
    """Mesnet tepkilerini temalanabilir HTML tablo olarak çiz (st.dataframe yerine;
    dataframe canvas tabanlı olduğu için gece modunda renklenmez)."""
    if not rows:
        return
    basliklar = list(rows[0].keys())
    thead = "".join(f"<th>{b}</th>" for b in basliklar)
    tbody = "".join(
        "<tr>" + "".join(f"<td>{r[b]}</td>" for b in basliklar) + "</tr>" for r in rows
    )
    st.markdown(
        f'<div class="pc-tablo-wrap"><table class="pc-tablo">'
        f"<thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>",
        unsafe_allow_html=True,
    )
