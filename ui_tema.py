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

import html
import time

import streamlit as st

# --- Moda göre CSS değişkenleri --------------------------------------------
_VARS = {
    "aydinlik": {
        "bg": "#FBFBFA", "surface": "#FFFFFF", "surface2": "#F3F2EF",
        "ink": "#1C1B19", "muted": "#6F6B64", "line": "rgba(28,27,25,0.10)",
        "acc": "#4338CA", "acc2": "#6366F1",
        # Parlama (glare) rengi moda göre TERS çalışır: aydınlıkta kart yüzeyi
        # beyaz olduğu için beyaz parlama görünmez — hafif aksan tonu kullanılır.
        "glare": "rgba(67,56,202,0.10)",
        # Shiny metin süpürmesi: TABAN renk + üzerinden geçen parlak BANT.
        # Aydınlıkta koyu zemin yok, o yüzden "parlama" ancak taban KOYULAŞTIRILIP
        # bant açılarak görünür olur. İlk denemede bant koyu (#1E1B4B) seçilmişti:
        # kontrast güvenliydi ama parlaklık farkı 0.067'de kalıyor, gecedeki
        # 0.587'nin dokuzda biri — kullanıcı "aydınlıkta hiçbir şey görünmüyor"
        # dedi, haklıydı. Şimdi fark 0.129. Ölçülen kontrastlar (zemin #F3F2EF):
        # taban 8.87, bant 3.99 — bant AA eşiğinin (4.5) hemen altında ama dar,
        # geçici ve yazının geri kalanı 8.87'de; alt çizgi de tabandan çizilir.
        "shine_taban": "#3730A3",
        "shine": "#6366F1",
        # Buton kenarı (SpecularButton'daki baseColor rolü: kenara yapışan koyu
        # şerit, kalınlık hissi verir). İstenen ton #0D0D0D; aydınlıkta düz siyah
        # beyaz/mor buton üzerinde sert bir çerçeve gibi durduğu için aynı ton
        # düşük opaklıkla kullanılır — kenar tanımlı ama sert değil.
        "btn_edge": "rgba(13,13,13,0.22)",
    },
    "gece": {
        "bg": "#15161B", "surface": "#1E2028", "surface2": "#262933",
        "ink": "#E9E7E2", "muted": "#9C988F", "line": "rgba(255,255,255,0.12)",
        "acc": "#818CF8", "acc2": "#A5B4FC",
        "glare": "rgba(255,255,255,0.10)",
        # Gecede taban zaten aksan; bant neredeyse beyaz (kontrast 4.86 → 12.98).
        "shine_taban": "#818CF8",
        "shine": "#EEF2FF",
        # Gecede istenen #0D0D0D düz kullanılır: yüzeyden koyu olduğu için
        # kenar gerçekten kalınlık/derinlik okunur.
        "btn_edge": "#0D0D0D",
    },
}


def _degiskenler(mod: str) -> str:
    v = _VARS.get(mod, _VARS["aydinlik"])
    return (
        "<style>:root{"
        f"--pc-bg:{v['bg']};--pc-surface:{v['surface']};--pc-surface2:{v['surface2']};"
        f"--pc-ink:{v['ink']};--pc-muted:{v['muted']};--pc-line:{v['line']};"
        f"--pc-acc:{v['acc']};--pc-acc2:{v['acc2']};--pc-glare:{v['glare']};"
        f"--pc-shine:{v['shine']};--pc-shine-taban:{v['shine_taban']};"
        f"--pc-btn-edge:{v['btn_edge']};"
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
.pc-hero {
  margin: 0.2rem 0 1.3rem; padding-bottom: 1.1rem; border-bottom: 1px solid var(--pc-line);
  display: flex; align-items: center; gap: 1.8rem;
}
.pc-hero__metin { flex: 1 1 auto; min-width: 0; }
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

/* Kenar çubuğu altbilgisi (kaynak kod + künye + geliştirici).
   `st.caption` DEĞİL, kendi bloğumuz: caption'ın puntosu sabit 14px ve
   Streamlit'in `stCaptionContainer * { color: ... }` kuralı içindeki bağlantıyı
   da soluklaştırıyordu. Kendi sınıfımızla hem punto hem renk bizde; shiny
   efekti de href yerine sınıfla hedeflenir (adres değişirse kural bozulmaz). */
.pc-altbilgi { font-size: 1rem; line-height: 1.55; color: var(--pc-muted); }
.pc-altbilgi a { color: var(--pc-acc); text-decoration: underline; }
.pc-altbilgi__kunye { display: inline-block; }

/* Shiny metin — react-bits ShinyText'ten uyarlandı (npx/React yok; efekt saf
   CSS). Özgününde saydam beyaz bir bant gri metnin üzerinden geçer; burada
   gradyan TABAN RENGİ de taşır, çünkü `background-clip: text` için dolgunun
   saydam olması gerekir ve `color` ile taban rengi veremeyiz (bkz.
   .pc-hero__title, aynı teknik).
   Yalnız geliştirici bağlantısı süpürülür — kaynak kod bağlantısı sade kalır
   ki AGPL 13. madde bağlantısı süslemeyle rekabet etmesin.
   Alt çizgi rengi AÇIKÇA verilir: currentColor saydam olduğu için çizgi
   kaybolur ve bağlantı bağlantı gibi durmazdı. */
.pc-altbilgi a.pc-altbilgi__shiny {  /* `.pc-altbilgi a`dan daha özgül olmalı:
     onun `text-decoration` KISAYOLU alt çizgi rengini currentColor'a sıfırlıyor
     ve çizgi tabanla farklı bir indigo çıkıyordu (ölçüldü: #4338CA vs #3730A3). */
  background: linear-gradient(100deg,
    var(--pc-shine-taban) 40%, var(--pc-shine) 50%, var(--pc-shine-taban) 60%);
  background-size: 220% 100%;
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
  text-decoration-color: var(--pc-shine-taban);
  animation: pcShiny 4.6s linear infinite;
}
@keyframes pcShiny { from { background-position: 180% 0; } to { background-position: -80% 0; } }
.pc-hero__line {
  margin-top: 0.9rem; height: 3px; width: 84px; border-radius: 3px; transform-origin: left center;
  background: linear-gradient(90deg, var(--pc-acc), var(--pc-acc2));
}

/* --- Hero görseli: yük altında iki açıklıklı sürekli kiriş --------------
   Jenerik bir arkaplan efekti yerine konunun kendisi çizilir. Şema ders
   kitabı düzenidir: düz çizgi = şekil değiştirmemiş eksen, kesikli eğri =
   sehim. Bu yüzden kiriş çizgisi SABİT kalır; yalnız yük ve sehim eğrisi
   nefes alır — animasyon "süs" değil, statik davranışın kendisi.
   Yalnız transform animasyonu (bu modülün ilkesi); SVG şeması `_kiris_svg`
   içinde Python ile üretilir, ölçüler oradaki sabitlere bağlıdır. */
.pc-hero__gorsel { flex: 0 0 auto; width: 260px; }
.pc-beam { display: block; width: 100%; height: auto; }
.pc-beam__kiris { stroke: var(--pc-ink); stroke-width: 2.4; fill: none; stroke-linecap: round; }
.pc-beam__mesnet { fill: var(--pc-muted); }
.pc-beam__zemin { stroke: var(--pc-muted); stroke-width: 1.4; }
.pc-beam__yuk { stroke: var(--pc-acc); fill: var(--pc-acc); stroke-width: 1.2; }
.pc-beam__sehim {
  stroke: var(--pc-acc2); stroke-width: 1.8; fill: none; stroke-dasharray: 4.5 3.5;
  /* Eğrinin sınır kutusunun ÜST kenarı kiriş kotudur (uç noktalar orada);
     oradan ölçeklenince mesnetler sabit kalır, yalnız sarkma derinleşir. */
  transform-box: fill-box; transform-origin: top;
}
/* Ortak ritim: yük bastıkça sehim derinleşir. `alternate` ile gidiş-dönüş
   sürekli olur; --pc-ease (expo-out) burada YANLIŞ olur — o tek yönlü bir
   varış eğrisi; nefes alan bir döngüde iki uçta da yumuşama gerekir. */
.pc-beam__yuk { animation: pcYukBas 3.4s ease-in-out infinite alternate; }
.pc-beam__sehim { animation: pcSehim 3.4s ease-in-out infinite alternate; }
@keyframes pcYukBas { from { transform: translateY(0); } to { transform: translateY(3px); } }
@keyframes pcSehim { from { transform: scaleY(0.16); } to { transform: scaleY(1); } }

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
/* Parlama (glare) süpürmesi — react-bits GlareHover'dan uyarlandı.
   Orijinal, dev bir arkaplanı `background-position` ile kaydırıyor; bizim kart
   oranlarımızda bant süpürüp çıkmak yerine solda park ediyordu (tarayıcıda
   ölçüldü). Bunun yerine sabit genişlikli bir bant `translateX` ile kaydırılır:
   davranış oran-bağımsız ve öngörülebilir, üstelik bu modülün ilkesine (yalnız
   transform/opacity animasyonu) uyar.
   Kart zaten position:relative + overflow:hidden; ::before üst aksan çubuğu
   için kullanıldığından ::after seçildi. pointer-events:none — tıklamayı engellemez.
   Geçiş YALNIZ :hover kuralında: fare ayrılınca bant anında başa döner, yoksa
   çıkışta ikinci (ters) bir süpürme görünürdü (orijinalin play-once varyantı). */
[data-testid="stMetric"]::after {
  content: ""; position: absolute; top: 0; bottom: 0; left: 0; width: 55%;
  pointer-events: none;
  background: linear-gradient(105deg, transparent 0%, var(--pc-glare) 50%, transparent 100%);
  transform: translateX(-160%);
}
@media (hover: hover) and (pointer: fine) {
  [data-testid="stMetric"]:hover { transform: translateY(-3px); box-shadow: var(--pc-sh-md); border-color: var(--pc-acc); }
  [data-testid="stMetric"]:hover::after {
    transform: translateX(250%);
    /* Bilerek --pc-ease DEĞİL: o eğri (expo-out) hareketin çoğunu ilk 180 ms'de
       bitiriyor; bant kart içinde yalnız ~190 ms görünüp "parlama" yerine "flaş"
       gibi okunuyordu (tarayıcıda ölçüldü). Süpürmede sabit hız doğru olan; bant
       iki uçta da kart dışında olduğundan linear'ın sert başlangıç/bitişi
       görünmez. Kart yükselmesi --pc-ease ile kalır — orada expo-out yerinde. */
    transition: transform 700ms linear;
  }
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

/* --- Specular buton kenarı (react-bits SpecularButton yaklaşımı) ---
   Orijinal WebGL'dir: ogl + GLSL shader, yuvarlatılmış dikdörtgenin SDF'sini
   alıp ışık açısına göre kenarda simetrik parlama üretir ve fareyi izler.
   Streamlit'te canvas'ı butonun içine koyup her rerun'da yeniden bağlamak
   gerektiğinden birebir taşınamaz; görünüm saf CSS ile yaklaşıklanır:
   conic-gradient + mask ile GERÇEK bir kenar şeridi çizilir, iki parlama yayı
   180° arayla konur (shader'ın simetrik specular'ı) ve hover'da döner.
   Fare takibi yerine hover — JS gerektirmeyen en yakın karşılık. */
@property --pc-spec-angle {
  syntax: "<angle>";
  initial-value: 0deg;
  inherits: false;
}
[data-testid="stFormSubmitButton"] button {
  position: relative;
  /* Kenara yapışan koyu şerit — shader'daki baseColor'ın karşılığı. */
  box-shadow: inset 0 0 0 1px var(--pc-btn-edge);
}
[data-testid="stFormSubmitButton"] button::before {
  content: ""; position: absolute; inset: 0; border-radius: inherit;
  padding: 1.5px;                      /* şerit kalınlığı (shader: uThickness) */
  background: conic-gradient(from var(--pc-spec-angle),
    transparent 0deg, var(--pc-spec) 22deg, transparent 52deg,
    transparent 180deg, var(--pc-spec) 202deg, transparent 232deg,
    transparent 360deg);
  /* İçi oyulur, yalnız kenar şeridi kalır. */
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
          mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
          mask-composite: exclude;
  opacity: 0;
  transition: opacity 260ms var(--pc-ease);
  pointer-events: none;
  /* Animasyon HER ZAMAN tanımlı, yalnız duraklatılmış. Hover'da eklenip
     çıkarıldığında opaklık geçişi bozuluyor ve şerit fare ayrılınca opacity:1'de
     takılı kalıyordu (tarayıcıda ölçüldü). Böylece hover yalnız play-state ve
     opacity'yi değiştirir; duraklatılmış animasyon kare üretmez. */
  animation: pcSpecular 2.6s linear infinite;
  animation-play-state: paused;
}
/* Parlama rengi sayfanın moru. Gönder butonları düz açık/koyu yüzeydedir; ana
   aksan orada doğrudan okunur. (Mor DOLGULU birincil buton denendi ve kaldırıldı:
   aynı aileden parlama dolgunun üzerine binince kayboluyordu.) */
[data-testid="stFormSubmitButton"] button { --pc-spec: var(--pc-acc); }
@media (hover: hover) and (pointer: fine) {
  [data-testid="stFormSubmitButton"] button:hover::before {
    opacity: 1;
    animation-play-state: running;
  }
}
@keyframes pcSpecular { to { --pc-spec-angle: 360deg; } }

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

/* --- Girdi ipucu metni --- */
/* Streamlit, sayı/metin girdisine odaklanınca alanın içine "Press Enter to submit
   form" / "Press Enter to apply" ipucunu basar (InputInstructions bileşeni). Hem
   İngilizce hem de girilen değerin üstüne binmesi rahatsız edici; her yerde gizle.
   Yalnız görsel gizleme — Enter ile gönderme çalışmaya devam eder. */
[data-testid="InputInstructions"] { display: none !important; }

/* --- Girdi odak halkası (Streamlit 1.59: baseweb sarmalayıcı yerine testid) --- */
[data-testid="stNumberInputContainer"]:focus-within,
[data-testid="stSelectbox"] div:has(> input):focus-within {
  border-color: var(--pc-acc) !important; box-shadow: 0 0 0 3px color-mix(in srgb, var(--pc-acc) 22%, transparent) !important;
}

/* --- Kenar çubuğu --- */
[data-testid="stSidebar"] { border-right: 1px solid var(--pc-line); }
/* Mobilde kenar çubuğu kapanınca Streamlit genişliğini ~1px yapar ama içerik
   kırpılmayıp ana içeriğin üstüne (harf harf sarmış etiketler) taşıyordu; kapalı
   durumda içeriği kes. Açık durumda (aria-expanded=true) etkilenmez. */
[data-testid="stSidebar"][aria-expanded="false"] { overflow: hidden !important; }
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
  /* Şema dar ekranda başlığı ezer; hover efektleri gibi mobilde kapatılır. */
  .pc-hero { display: block; }
  .pc-hero__gorsel { display: none; }
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
  /* Parlama tamamen kapatılır (kayan gradyan hareket algısı yaratır). */
  [data-testid="stMetric"]::after { display: none !important; }
  /* Specular kenar KALIR ama dönmez: statik bir kenar vurgusu hareket değildir,
     butonun etkileşilebilir olduğunu göstermeye devam eder. */
  [data-testid="stFormSubmitButton"] button:hover::before { animation-play-state: paused !important; }
  /* Hero şeması KALIR, donar: tam sarkmış haliyle okunur bir statik şemadır. */
  .pc-beam__yuk, .pc-beam__sehim { animation: none !important; }
  /* Shiny bağlantı: süpürme durur, düz taban rengine döner (gradyan dolgusu
     kaldırılmazsa metin donmuş bir bant deseniyle kalırdı). */
  .pc-altbilgi__shiny {
    animation: none !important; background: none !important;
    -webkit-text-fill-color: var(--pc-shine-taban) !important;
  }
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
/* Kenar çubuğu aç/kapat oku (»/«) gece modunda koyu kalıp görünmüyordu. İkon bir
   Material Symbols glifi; color/fill override'ı bazı mobil tarayıcılarda tutmadığı
   için ikonun PİKSELLERİNİ ters çeviriyoruz (koyu ok → açık ok) — ikonun nasıl
   boyandığından bağımsız, kurşun geçirmez. Buton zemini şeffaf; yalnız ikon döner. */
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"],
[data-testid="stMainMenuButton"] {
  filter: invert(1) brightness(1.5) !important;
}
/* Deploy butonu. ⋮ menüsünün yanında durur ama piksel-ters çevirme AİLESİNE
   GİRMEZ: metin taşıdığı için invert edilirse zemin de dönüp açık bir kutu
   olurdu. Yazı rengi doğrudan verilir (ölçüm: rgb(28,27,25) — açık temanın
   metni, şeffaf başlık üzerinde okunmuyordu). stMainMenuButton'a bu kural
   BULAŞMAMALI; oradaki ikon zaten ters çevriliyor, üstüne açık renk verilirse
   invert onu tekrar koyuya döndürür. */
[data-testid="stAppDeployButton"], [data-testid="stAppDeployButton"] * {
  color: var(--pc-ink) !important;
}
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
[data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stMultiSelect"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div > div,
[data-baseweb="textarea"], [data-baseweb="textarea"] textarea {
  background-color: var(--pc-surface2) !important; border-color: var(--pc-line) !important;
}
/* Çoklu seçim (İç mafsallı düğümler): kutu yüzeyi yukarıda, metin ve seçilen
   değer çipleri burada. stSelectbox kuralları bunu kapsamıyordu — kutu gece
   modunda beyaz kalıyordu. Çip aksan rengiyle dolu olduğu için üzerindeki yazı
   her iki modda da beyazdır (değişkene bağlanmaz). */
[data-testid="stMultiSelect"], [data-testid="stMultiSelect"] input,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
  color: var(--pc-ink) !important;
}
/* "Choose options" ipucu baseweb'de input placeholder'ı DEĞİL, ayrı bir <div>
   ve rengini açık temanın metninden alıyor (DOM'dan ölçüldü: rgba(28,27,25,.6))
   — koyu zeminde okunmuyordu. Emotion sınıfları (st-cm, st-bp …) sürüm sürüm
   değiştiği için yol üzerinden hedeflenir. */
[data-testid="stMultiSelect"] [data-baseweb="select"] div {
  color: var(--pc-muted) !important;
}
/* Seçilen değer çipleri. Yol TAM yazılır ki yukarıdaki kuraldan daha spesifik
   olsun; aksi halde çip yazısı da sönükleşirdi (ikisi de !important, kazananı
   spesifiklik belirler). */
[data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="tag"],
[data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="tag"] * {
  background-color: var(--pc-acc) !important; color: #FFFFFF !important;
}
[data-testid="stNumberInputField"], [data-baseweb="textarea"] textarea,
[data-testid="stSelectbox"] div:has(> input), [data-testid="stSelectbox"] input {
  color: var(--pc-ink) !important;
}
/* Placeholder AYRI bir sözde-öğedir; kural yazılmazsa Streamlit'in AÇIK tema
   rengi kalır ve gece modunda kutunun içindeki ipucu metni ("0") okunmaz olur. */
[data-testid="stNumberInputField"]::placeholder,
[data-baseweb="textarea"] textarea::placeholder,
[data-testid="stSelectbox"] input::placeholder,
[data-testid="stMultiSelect"] input::placeholder {
  color: var(--pc-muted) !important; opacity: 1;
}
[data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"] {
  background-color: var(--pc-surface) !important; color: var(--pc-ink) !important;
}
/* Adım (−/+) ve temizle (⊗) ikonları. Streamlit ikon rengini SATIR İÇİ verir:
   etkinken "inherit", DEVRE DIŞIYKEN açık temanın fadedText40'ı (NumberInput
   bundle: color: X ? `inherit` : o.colors.fadedText40). Bu yüzden alan boşken
   (adım düğmesi devre dışı) ikonlar gece modunda kayboluyordu. İkon öğesinin
   kendisi hedeflenip !important ile bastırılır; devre dışı olan sönük ama
   görünür kalsın diye muted, etkin olan ink. */
[data-testid="stNumberInputStepUp"] *, [data-testid="stNumberInputStepDown"] *,
[data-testid="stNumberInputClearButton"], [data-testid="stNumberInputClearButton"] * {
  color: var(--pc-muted) !important;
}
/* fill YALNIZ gerçek şekil path'lerine verilir. Temizle (⊗) ikonunun SVG'si iki
   path içerir: önce `fill="none"` olan 24×24'lük hizalama karesi, sonra asıl
   çarpı şekli. `* { fill: currentColor !important }` birincinin fill="none"unu
   da eziyor ve alana değer girilir girilmez sağda İÇİ DOLU KARE çıkıyordu
   (DOM'dan ölçüldü: hesaplanan fill rgb(156,152,143)). Adım ikonlarında tek
   path var, onlar zaten svg'nin currentColor'ını miras alır. */
[data-testid="stNumberInputStepUp"] path:not([fill="none"]),
[data-testid="stNumberInputStepDown"] path:not([fill="none"]),
[data-testid="stNumberInputClearButton"] path:not([fill="none"]) {
  fill: currentColor !important;
}
/* Selectbox / multiselect kutusundaki açılır ok (∨) ve temizle (⊗) ikonları.
   Bunlar kutunun İÇİNDE, `aria-label="Open"`/"Clear value" sarmalayıcılarında
   durur ve rengini açık temadan alır (ölçüm: rgb(28,27,25) = #1C1B19), yani
   koyu kutuda siyah kalıyordu. Ok SVG'si de temizle ikonu gibi `fill="none"`
   olan hizalama path'i taşır — fill yine yalnız gerçek şekle verilir, yoksa
   ok içi dolu kareye döner. */
[data-testid="stSelectbox"] svg, [data-testid="stMultiSelect"] svg {
  color: var(--pc-muted) !important;
}
[data-testid="stSelectbox"] svg path:not([fill="none"]),
[data-testid="stMultiSelect"] svg path:not([fill="none"]) {
  fill: currentColor !important;
}
[data-testid="stNumberInputStepUp"]:not(:disabled) *,
[data-testid="stNumberInputStepDown"]:not(:disabled) * {
  color: var(--pc-ink) !important;
}
/* Açılır listeler (selectbox + multiselect). Portal ile <body> altına basıldığı
   için app kapsayıcısını hedefleyen kurallar ulaşmıyordu; testid/baseweb ile
   doğrudan hedeflenir. DOM'dan ölçülen açık tema değerleri: popover #F3F2EF,
   liste #FBFBFA, seçenek metni #1C1B19. */
[data-baseweb="popover"], [data-testid="stSelectboxVirtualDropdown"],
[data-testid="stSelectboxVirtualDropdownEmpty"] {
  background-color: var(--pc-surface2) !important;
}
/* Seçenekler <li> DEĞİL: Streamlit 1.59 sanal listeyi react-aria ile çizer ve
   her seçenek `role="option"` taşıyan bir <div>'dir (DOM'dan ölçüldü: li sayısı
   0, seçenek rengi rgb(28,27,25) = açık temanın #1C1B19'u). Yalnız `li`
   hedefleyen kural hiç tutmuyordu; popover zemini koyu olduğu için yazı
   okunmuyordu. `li` yolu multiselect gibi hâlâ baseweb menüsü kullanan
   bileşenler için korunur. */
[data-testid="stSelectboxVirtualDropdown"] [role="option"],
[data-testid="stSelectboxVirtualDropdown"] [role="option"] *,
[data-baseweb="popover"] [role="option"],
[data-baseweb="popover"] [role="option"] *,
[data-baseweb="popover"] li, [data-baseweb="popover"] li *,
[data-testid="stSelectboxVirtualDropdown"] li,
[data-testid="stSelectboxVirtualDropdown"] li *,
[data-testid="stSelectboxVirtualDropdownEmpty"],
[data-testid="stSelectboxVirtualDropdownEmpty"] li {
  color: var(--pc-ink) !important;
}
[data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] li:hover,
[data-testid="stSelectboxVirtualDropdown"] li:hover {
  background-color: color-mix(in srgb, var(--pc-acc) 22%, transparent) !important;
}

/* İkincil butonlar / indirme / form gönder.
   Form gönder butonunda `kind` değeri "secondary" DEĞİL, "secondaryFormSubmit"
   (DOM'dan doğrulandı: kind=secondaryFormSubmit, data-testid=
   stBaseButton-secondaryFormSubmit). Eski [kind="secondary"] seçicisi bu yüzden
   hiçbir şeye uymuyor, "Mafsal ekle" gece modunda beyaz kalıyordu. Yalnız
   ikincil hedeflenir; birincil (mor "Yük ekle") vurgu rengini korur. */
.stButton > button, .stDownloadButton > button,
[data-testid="stFormSubmitButton"] button[kind="secondaryFormSubmit"] {
  background-color: var(--pc-surface) !important; color: var(--pc-ink) !important; border-color: var(--pc-line) !important;
}
/* Form ve genişleyen yüzeyi. `details` gövdeyi koyulaştırıyor ama `summary`
   (başlık çubuğu) kendi açık zeminini taşıdığı için ayrıca bastırılmalı. */
[data-testid="stForm"] { background-color: var(--pc-surface) !important; border-color: var(--pc-line) !important; }
[data-testid="stExpander"] details, [data-testid="stExpander"] summary {
  background-color: var(--pc-surface) !important;
}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: var(--pc-ink) !important; }
/* `help=` ipuçları. Açılır listeler gibi portal ile <body> altına basılır, bu
   yüzden app kapsayıcısını hedefleyen kurallar ulaşmaz. Ölçülen açık tema
   değerleri: zemin rgb(243,242,239) = #F3F2EF; yazı ise genel markdown
   kuralından --pc-ink (rgb(233,231,226)) alıyordu — açık üstüne açık, kontrast
   1.05:1, ipucu tamamen kayboluyordu. Testid'ler Streamlit 1.59 paketinden
   doğrulandı (stTooltipContent / stTooltipIcon). */
[data-testid="stTooltipContent"], [data-baseweb="tooltip"] {
  background-color: var(--pc-surface2) !important;
  border: 1px solid var(--pc-line) !important;
}
[data-testid="stTooltipContent"], [data-testid="stTooltipContent"] *,
[data-baseweb="tooltip"], [data-baseweb="tooltip"] * {
  color: var(--pc-ink) !important;
}
/* Yardım ikonunun kendisi: şekil path'i boyanmadığı için ekranda sönük bir
   nokta kalıyordu — selectbox okundaki `path:not([fill="none"])` deseni. */
[data-testid="stTooltipIcon"] svg { color: var(--pc-muted) !important; }
[data-testid="stTooltipIcon"] svg path:not([fill="none"]) { fill: currentColor !important; }
</style>"""


# --- Yalnız ilk yüklemede: giriş (fade-up) animasyonu -----------------------
_GIRIS_CSS = """<style>
@keyframes pcFadeUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
@keyframes pcGrow  { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes pcFadeIn { from { opacity: 0; } to { opacity: 1; } }
/* Giriş animasyonları YALNIZ masaüstünde (min-width:641px). Mobilde bu
   animasyonlar ilk yüklemede kenar çubuğu yerleşimini bozuyordu; tema değişince
   rerun'da _GIRIS_CSS yeniden enjekte edilmediğinden sorun "kendiliğinden"
   kayboluyordu — kök neden buydu. Mobilde animasyonsuz, temiz açılır. */
@media (min-width: 641px) {
  [data-testid="stMainBlockContainer"] { animation: pcFadeUp 560ms var(--pc-ease) both; }
  [data-testid="stSidebar"] { animation: pcFadeIn 560ms var(--pc-ease) both; }
  .pc-hero__line { animation: pcGrow 720ms var(--pc-ease) 140ms both; }
}
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


# Hero şemasının geometrisi (SVG kullanıcı birimi). Mesnet x'leri ve kiriş
# kotu; CSS'teki animasyon bunlara değil, sınır kutusuna göre çalışır.
_HERO_A, _HERO_B, _HERO_C, _HERO_Y = 24.0, 130.0, 236.0, 46.0
# CSS'teki `animation-duration` ile AYNI olmalı (bkz. pcYukBas/pcSehim).
# `alternate` olduğu için tam tur = gidiş + dönüş = 2×süre.
_HERO_SURE = 3.4


def _kiris_svg(aria: str) -> str:
    """Hero görseli: iki açıklıklı sürekli kiriş şeması (yayılı yük + sehim).

    Sehim eğrisi gerçek biçimi taklit eder: simetrik iki açıklıkta orta
    mesnette teğet YATAY olur, bu yüzden B'ye komşu kontrol noktaları kiriş
    kotundadır (aksi halde orta mesnette gerçekte olmayan bir kırık görünür).
    """
    a, b, c, y = _HERO_A, _HERO_B, _HERO_C, _HERO_Y
    # Streamlit her rerun'da markdown düğümünü yeniden kurar; CSS animasyonu da
    # sıfırdan başlar ve döngü görünür biçimde zıplar (tarayıcıda görüldü).
    # Çözüm: fazı duvar saatinden türet ve NEGATİF animation-delay ile ilerisine
    # sar. Eleman yeni doğsa bile aynı ana denk gelir, yani süreklilik korunur.
    # Sunucu-istemci gecikmesi kadar sapar (~ms); 6.8 s'lik turda görünmez.
    faz = f'style="animation-delay:{-(time.time() % (2 * _HERO_SURE)):.2f}s"'
    # Yayılı yük: üst bant + eşit aralıklı oklar (uçları da dahil).
    n = 11
    oklar = [f'<line x1="{a}" y1="17" x2="{c}" y2="17" />']
    for i in range(n + 1):
        x = round(a + i * (c - a) / n, 2)
        oklar.append(f'<line x1="{x}" y1="17" x2="{x}" y2="37.5" />')
        oklar.append(
            f'<polygon points="{x - 2.6},36 {x + 2.6},36 {x},41.5" stroke="none" />'
        )
    mesnetler = "".join(
        f'<polygon class="pc-beam__mesnet" '
        f'points="{x},{y} {x - 7},{y + 13} {x + 7},{y + 13}" />'
        f'<line class="pc-beam__zemin" '
        f'x1="{x - 11}" y1="{y + 14.5}" x2="{x + 11}" y2="{y + 14.5}" />'
        for x in (a, b, c)
    )
    sehim = (
        f'M{a} {y} C{a + 32} {y + 36} {b - 22} {y} {b} {y} '
        f'C{b + 22} {y} {c - 32} {y + 36} {c} {y}'
    )
    return (
        '<svg class="pc-beam" viewBox="6 8 248 56" role="img" '
        f'aria-label="{aria}">'
        f'<g class="pc-beam__yuk" stroke-linecap="round" {faz}>{"".join(oklar)}</g>'
        f'{mesnetler}'
        f'<line class="pc-beam__kiris" x1="{a}" y1="{y}" x2="{c}" y2="{y}" />'
        f'<path class="pc-beam__sehim" d="{sehim}" {faz} />'
        "</svg>"
    )


def hero_baslik(baslik: str, altyazi: str, eyebrow: str, sema_aria: str):
    """st.title yerine animasyonlu, gradyan-aksanlı hero başlık bloğu çiz.

    Metinlerin tamamı (şemanın aria etiketi dahil) dışarıdan verilir; bu modül
    dil kataloğunu tanımaz (bkz. ui_dil.py).
    """
    st.markdown(
        f'<div class="pc-hero">'
        f'<div class="pc-hero__metin">'
        f'<div class="pc-hero__eyebrow">{eyebrow}</div>'
        f'<h1 class="pc-hero__title">{baslik}</h1>'
        f'<p class="pc-hero__sub">{altyazi}</p>'
        f'<div class="pc-hero__line"></div>'
        f'</div>'
        f'<div class="pc-hero__gorsel">{_kiris_svg(sema_aria)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def altbilgi(kaynak_metin: str, kaynak_url: str, atif: str,
             gelistiren: str, ad: str, profil_url: str):
    """Kenar çubuğu altbilgisi: kaynak kod bağlantısı, künye, geliştirici.

    `st.caption` yerine kendi bloğumuz — gerekçesi CSS'te (.pc-altbilgi).
    Kaynak kod bağlantısı AGPL 13. maddesinin gereği olduğu için sade ve
    okunur bırakılır; süpürme (shiny) yalnız geliştirici bağlantısındadır.
    Metinlerin tamamı dışarıdan verilir; bu modül dil kataloğunu tanımaz.
    """
    kacir = html.escape
    st.markdown(
        f'<div class="pc-altbilgi">'
        f'<a href="{kacir(kaynak_url, quote=True)}" target="_blank" '
        f'rel="noopener">{kacir(kaynak_metin)}</a><br>'
        f'<span class="pc-altbilgi__kunye">{kacir(atif)}</span><br>'
        f'{kacir(gelistiren)}: '
        f'<a class="pc-altbilgi__shiny" href="{kacir(profil_url, quote=True)}" '
        f'target="_blank" rel="noopener">{kacir(ad)}</a>'
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
