"""Arayüz metinleri — Türkçe/İngilizce katalog.

Sunum katmanının TÜM kullanıcıya görünen metinleri buradadır; `app.py` ve
`ui_cizim.py` sabit dize yazmaz. Çekirdeğin kendi hata mesajları ayrıdır
(`core/mesajlar.py`) — orada da aynı desen kullanılır.

Streamlit'e bağımlı DEĞİLDİR: dil, çağıran katmandan açık parametre olarak
geçirilir (`cevir(dil, anahtar, ...)`). `app.py` kolaylık olsun diye bunu
`t(...)` adıyla kendine bağlar. Böylece `ui_cizim.py` tarayıcısız test
edilebilir kalır.

Anahtar düzeni: nokta ile gruplanır — `mesnet.pin`, `param.w`, `yuk.udl`,
`ipucu.udl`. Birimler (kN, m, kNm²) çeviriye girmez, dilden bağımsızdır.

Eksik anahtar/dil sessizce Türkçeye düşer; yarım çeviri arayüzü kırmaz.
"""

# Dil kodu -> seçim kutusunda görünen ad (kendi dilinde yazılır: bir kullanıcı
# yanlış dilde kalsa bile kendi dilini tanıyıp geri dönebilsin).
DILLER = {"tr": "Türkçe", "en": "English"}
VARSAYILAN_DIL = "tr"

_TR = {
    # --- sayfa / hero ---
    "sayfa_basligi": "PyCBA Kiriş Analizi",
    "hero.eyebrow": "Yapı statiği · sürekli kiriş",
    "hero.baslik": "Sürekli Kiriş Analizi",
    "hero.altyazi": "PyCBA çekirdeğiyle mesnet tepkileri, kesit tesirleri ve "
                    "sehim — anında, etkileşimli diyagramlarla.",
    "sema.aria": "İki açıklıklı sürekli kiriş: yayılı yük altında sehim",

    # --- kenar çubuğu: genel ---
    "gece_modu": "🌙 Gece modu",
    "dil_secimi": "🌐 Dil",

    # --- 1. geometri ---
    "bolum.geometri": "1. Geometri",
    "aciklik_sayisi": "Açıklık sayısı",

    # --- 2. mesnetler ---
    "bolum.mesnetler": "2. Mesnetler",
    "dugum_no": "Düğüm {n}",
    "mesnet.pin": "Mafsal (pin)",
    "mesnet.roller": "Kayıcı (roller)",
    "mesnet.fixed": "Ankastre (fixed)",
    "mesnet.free": "Serbest (free)",
    "mafsal.coklu_secim": "İç mafsallı düğümler (Gerber)",
    "mafsal.yardim": "Seçilen düğümde kiriş moment aktarmaz; şemada içi boş "
                     "daire ile gösterilir.",
    "mafsal.baslik": "Açıklık içi mafsal",
    "mafsal.aciklama": "Mafsalı mesnet hizasında değil, açıklığın ortasında bir "
                       "noktada istiyorsan buradan ekle. Açıklık o noktadan "
                       "otomatik bölünür.",
    "mafsal.aciklik_no": "Mafsalın olduğu açıklık no",
    "mafsal.konum": "Konum a [m] — sol uçtan (0 < a < {L:g})",
    "mafsal.ekle": "➕ Mafsal ekle",
    "mafsal.konum_hatasi": "Konum açıklığın içinde olmalı (0 < a < {L:g} m). "
                           "Mesnet hizasındaki mafsal için üstteki düğüm "
                           "seçimini kullan.",
    "mafsal.zaten_var": "Bu mafsal zaten tanımlı.",
    "mafsal.satir": "Açıklık {sp} · a = {a:g} m",
    "cokme.baslik": "Mesnet çökmesi",
    "cokme.aciklama": "Bir mesnedin düşey olarak yer değiştirdiği durum (zemin "
                      "oturması, kazık çökmesi). Değer AŞAĞI yönde pozitiftir; "
                      "yukarı kalkma için eksi girin. Kesit tesiri yalnız "
                      "hiperstatik sistemde doğar.",
    "cokme.alan": "Δ Düğüm {n} [mm]",
    "cokme.yardim": "Aşağı çökme pozitif, yukarı kalkma negatiftir.",
    "cokme.mesnet_yok": "Çökme verilebilecek mesnet yok — tüm düğümler serbest.",

    # --- 3. yükler ---
    "bolum.yukler": "3. Yükler",
    "aciklik_no": "Açıklık no",
    "yuk_tipi": "Yük tipi",
    "secili_aciklik": "(Seçili açıklık: L = {L:g} m)",
    "yuk.ekle": "➕ Yük ekle",
    "yuk.siddet_sifir": "Yük şiddeti 0 — sıfırdan farklı bir değer girin.",
    "yuk.siddet_sifir_duzenle": "Yük şiddeti 0 olamaz — silmek için 🗑️ kullanın.",

    # yük tipi adları (core.LOAD_TYPES anahtarlarıyla aynı sonek)
    "yuk.udl": "Yayılı yük (UDL)",
    "yuk.point": "Tekil yük",
    "yuk.partial_udl": "Kısmi yayılı yük",
    "yuk.moment": "Moment",
    "yuk.trapezoid": "Trapez yük",
    "yuk.axial_point": "Eksenel tekil yük",
    "yuk.axial_udl": "Eksenel yayılı yük",

    # yük parametresi etiketleri (birim ayrı; app.PARAM_UNITS)
    "param.w": "Yayılı yük w",
    "param.w1": "Başlangıç şiddeti w₁",
    "param.w2": "Bitiş şiddeti w₂",
    "param.P": "Yük P",
    "param.M": "Moment M",
    "param.a": "Konum a — açıklığın sol ucundan",
    "param.c": "Yayılı uzunluk c",
    "param.N": "Eksenel yük N (+ sağa)",
    "param.n": "Eksenel yayılı yük n (+ sağa)",

    # yük tipine göre konum ipucu
    "ipucu.udl": "Tüm açıklığa yayılır; konum girilmez.",
    "ipucu.point": "a: yükün açıklığın sol ucundan uzaklığı "
                   "(örn. orta nokta için L/2).",
    "ipucu.partial_udl": "a: sol uçtan başlangıç uzaklığı, c: yükün yayıldığı "
                         "uzunluk (a+c ≤ L).",
    "ipucu.moment": "a: momentin açıklığın sol ucundan uzaklığı.",
    "ipucu.trapezoid": "a=0 ve c=0 girilirse tüm açıklığa yayılır; kısmi için "
                       "a ve c verin.",
    "ipucu.axial_point": "Kiriş eksenine (x) paralel tekil yük; + değer sağa. "
                         "a: sol uçtan uzaklık. Şemada mavi yatay ok, sonuçta "
                         "N diyagramı.",
    "ipucu.axial_udl": "Kiriş eksenine (x) paralel, tüm açıklığa yayılı yük; "
                       "+ değer sağa. Şemada mavi yatay oklar, sonuçta "
                       "N diyagramı.",

    # --- 4. görünüm ---
    "bolum.gorunum": "4. Görünüm",
    "gorunum.aciklama": "Kapatılan grafik hiç çizilmez; sayısal sonuçlar "
                        "etkilenmez.",
    "gorunum.sema": "Kiriş şeması",
    "gorunum.N": "Normal kuvvet (N)",
    "gorunum.V": "Kesme kuvveti (V)",
    "gorunum.M": "Moment (M)",
    "gorunum.D": "Sehim",

    # --- yük listesi ---
    "liste.baslik": "Tanımlı yükler",
    "liste.bos": "Henüz yük eklenmedi — kenar çubuğundan ekleyin.",
    "liste.duzenle_ipucu": "Bir yükü düzenlemek için başlığına tıklayıp açın.",
    "liste.satir": "**{i}.** {ad} — Açıklık {sp} — {ayrinti}",
    "liste.kaydet": "💾 Kaydet",
    "liste.sil": "🗑️ Sil",

    # --- şema / sonuçlar ---
    "sema.baslik": "Kiriş şeması",
    "sema.eksen_x": "Kiriş boyunca uzaklık [m]",
    "sema.legend.dusey": "Düşey yük",
    "sema.legend.eksenel": "Eksenel yük",
    "sema.legend.tepki": "Mesnet tepkisi",
    # Birim ETİKETTE değil legend'da: şemada mesnet başına düşen yatay yer,
    # açıklık sayısıyla daralıyor ve "Δ = 10 mm" komşusuyla çakışıyordu. Etiket
    # yalnız ok + değerdir (bkz. ui_cizim.ciz_cokmeler), birimi legend taşır —
    # diyagramlarda eksen başlığının birimi taşıması gibi.
    "sema.legend.cokme": "Mesnet çökmesi [mm]",
    "sonuclar.baslik": "Sonuçlar",
    "sonuclar.yuk_ekleyin": "Sonuçlar ve mesnet tepkileri için en az bir yük "
                            "ekleyin ya da bir mesnet çökmesi tanımlayın.",
    "uyari.cokme_izostatik": "Sistem izostatik (statik belirsizlik derecesi 0): "
                             "mesnet çökmesi kirişi rijit olarak yer değiştirir, "
                             "kesit tesiri doğurmaz. Moment ve kesme "
                             "diyagramlarının sıfır çıkması beklenen davranıştır; "
                             "sehim diyagramı yer değiştirmeyi gösterir.",
    "uyari.ea": "Eksenel sistem hiperstatik (birden çok yatayda tutulu mesnet) "
                "ve açıklıkların kesiti farklı. Çözücü eksenel rijitliği (EA) "
                "tüm açıklıklarda eşit varsayar; yatay tepkilerin paylaşımı bu "
                "yüzden yaklaşıktır. Normal kuvvet diyagramının şekli ve düşey "
                "sonuçlar bundan etkilenmez.",

    # metrik kartları
    # Kart başlığı, gösterilen ekstreme göre seçilir (bkz. app._kart):
    # yöneten maks ise "kart.maks", min ise "kart.min_baslik". Caption'daki
    # ikinci satır da buna göre "kart.min" ya da "kart.maks_alt" olur.
    "kart.maks": "Maks. {ad} [{birim}]",
    "kart.min_baslik": "Min. {ad} [{birim}]",
    "kart.konum": "@ x = {x:.2f} m",
    "kart.min": "Min. {deger} @ x = {x:.2f} m",
    "kart.maks_alt": "Maks. {deger} @ x = {x:.2f} m",
    "buyukluk.moment": "moment",
    "buyukluk.kesme": "kesme",
    "buyukluk.sehim": "sehim",
    "buyukluk.normal": "normal",

    # diyagram panelleri
    "diyagram.baslik": "Kesit Tesirleri Diyagramları",
    "diyagram.eksen_x": "Kiriş boyunca konum [m]",
    "diyagram.hepsi_kapali": "Tüm diyagramlar kapalı — kenar çubuğundaki "
                             "**4. Görünüm** bölümünden açabilirsin. Metrikler, "
                             "mesnet tepkileri ve CSV indirme etkilenmez.",
    "panel.normal": "Normal",
    "panel.kesme": "Kesme",
    "panel.moment": "Moment",
    "panel.sehim": "Sehim",

    # CSV
    "csv.diyagram_buton": "⬇️ Diyagram verileri (CSV)",
    "csv.diyagram_dosya": "diyagram_moment_kesme_sehim.csv",
    "csv.normal_buton": "⬇️ Normal kuvvet verileri (CSV)",
    "csv.normal_dosya": "diyagram_normal_kuvvet.csv",
    "csv.x": "x [m]",
    "csv.moment": "Moment [kNm]",
    "csv.kesme": "Kesme [kN]",
    "csv.sehim": "Sehim [mm]",
    "csv.normal": "Normal [kN]",

    # --- kenar çubuğu altbilgisi (lisans) ---
    # AGPL 13. madde: yazılım ağ üzerinden kullandırıldığında kullanıcılara
    # kaynak koda erişim SUNULMALI. Depodaki LICENSE/NOTICE tek başına yetmez,
    # bağlantının çalışan uygulamada olması gerekir (bkz. NOTICE).
    "lisans.kaynak": "Kaynak kodu (AGPL-3.0)",
    "lisans.atif": "Hesap çekirdeği PyCBA — © Colin Caprani, AGPL-3.0",
    # Geliştirici adı çeviriye girmez (özel ad); yalnız etiketi çevrilir.
    "lisans.gelistiren": "Geliştiren",

    # tepki tablosu
    "tepki.baslik": "Mesnet tepkileri",
    "tepki.dugum": "Düğüm",
    "tepki.konum": "Konum [m]",
    "tepki.dusey": "Düşey tepki [kN]",
    "tepki.yatay": "Yatay tepki [kN]",
    "tepki.moment": "Moment tepkisi [kNm]",
}

_EN = {
    "sayfa_basligi": "PyCBA Beam Analysis",
    "hero.eyebrow": "Structural statics · continuous beam",
    "hero.baslik": "Continuous Beam Analysis",
    "hero.altyazi": "Support reactions, internal forces and deflection powered "
                    "by the PyCBA core — instantly, with interactive diagrams.",
    "sema.aria": "Two-span continuous beam: deflection under a distributed load",

    "gece_modu": "🌙 Dark mode",
    "dil_secimi": "🌐 Language",

    "bolum.geometri": "1. Geometry",
    "aciklik_sayisi": "Number of spans",

    "bolum.mesnetler": "2. Supports",
    "dugum_no": "Node {n}",
    "mesnet.pin": "Pinned (pin)",
    "mesnet.roller": "Roller (roller)",
    "mesnet.fixed": "Fixed (fixed)",
    "mesnet.free": "Free (free)",
    "mafsal.coklu_secim": "Nodes with internal hinges (Gerber)",
    "mafsal.yardim": "The beam transfers no moment at the selected node; shown "
                     "as a hollow circle in the schematic.",
    "mafsal.baslik": "Hinge within a span",
    "mafsal.aciklama": "Use this if you want the hinge somewhere inside a span "
                       "rather than at a support. The span is split "
                       "automatically at that point.",
    "mafsal.aciklik_no": "Span containing the hinge",
    "mafsal.konum": "Position a [m] — from the left end (0 < a < {L:g})",
    "mafsal.ekle": "➕ Add hinge",
    "mafsal.konum_hatasi": "The position must lie inside the span "
                           "(0 < a < {L:g} m). For a hinge at a support, use the "
                           "node selection above.",
    "mafsal.zaten_var": "This hinge is already defined.",
    "mafsal.satir": "Span {sp} · a = {a:g} m",
    "cokme.baslik": "Support settlement",
    "cokme.aciklama": "A support that moves vertically (soil settlement, pile "
                      "movement). A positive value means DOWNWARD; enter a "
                      "negative value for uplift. Internal forces arise only in "
                      "a statically indeterminate system.",
    "cokme.alan": "Δ Node {n} [mm]",
    "cokme.yardim": "Downward settlement is positive, uplift is negative.",
    "cokme.mesnet_yok": "No support can settle — every node is free.",

    "bolum.yukler": "3. Loads",
    "aciklik_no": "Span no",
    "yuk_tipi": "Load type",
    "secili_aciklik": "(Selected span: L = {L:g} m)",
    "yuk.ekle": "➕ Add load",
    "yuk.siddet_sifir": "Load magnitude is 0 — enter a non-zero value.",
    "yuk.siddet_sifir_duzenle": "Load magnitude cannot be 0 — use 🗑️ to delete it.",

    "yuk.udl": "Uniformly distributed load (UDL)",
    "yuk.point": "Point load",
    "yuk.partial_udl": "Partial distributed load",
    "yuk.moment": "Moment",
    "yuk.trapezoid": "Trapezoidal load",
    "yuk.axial_point": "Axial point load",
    "yuk.axial_udl": "Axial distributed load",

    "param.w": "Distributed load w",
    "param.w1": "Start intensity w₁",
    "param.w2": "End intensity w₂",
    "param.P": "Load P",
    "param.M": "Moment M",
    "param.a": "Position a — from the left end of the span",
    "param.c": "Loaded length c",
    "param.N": "Axial load N (+ to the right)",
    "param.n": "Axial distributed load n (+ to the right)",

    "ipucu.udl": "Spread over the whole span; no position needed.",
    "ipucu.point": "a: distance of the load from the left end of the span "
                   "(e.g. L/2 for midspan).",
    "ipucu.partial_udl": "a: start distance from the left end, c: length over "
                         "which the load is spread (a+c ≤ L).",
    "ipucu.moment": "a: distance of the moment from the left end of the span.",
    "ipucu.trapezoid": "Enter a=0 and c=0 to spread it over the whole span; "
                       "give a and c for a partial load.",
    "ipucu.axial_point": "Point load parallel to the beam axis (x); positive "
                         "means to the right. a: distance from the left end. "
                         "Shown as a blue horizontal arrow in the schematic and "
                         "as an N diagram in the results.",
    "ipucu.axial_udl": "Load parallel to the beam axis (x), spread over the whole "
                       "span; positive means to the right. Shown as blue "
                       "horizontal arrows in the schematic and as an N diagram "
                       "in the results.",

    "bolum.gorunum": "4. Display",
    "gorunum.aciklama": "A chart that is turned off is not drawn at all; "
                        "numerical results are unaffected.",
    "gorunum.sema": "Beam schematic",
    "gorunum.N": "Axial force (N)",
    "gorunum.V": "Shear force (V)",
    "gorunum.M": "Moment (M)",
    "gorunum.D": "Deflection",

    "liste.baslik": "Defined loads",
    "liste.bos": "No loads added yet — add one from the sidebar.",
    "liste.duzenle_ipucu": "Click a load's title to open and edit it.",
    "liste.satir": "**{i}.** {ad} — Span {sp} — {ayrinti}",
    "liste.kaydet": "💾 Save",
    "liste.sil": "🗑️ Delete",

    "sema.baslik": "Beam schematic",
    "sema.eksen_x": "Distance along beam [m]",
    "sema.legend.dusey": "Vertical load",
    "sema.legend.eksenel": "Axial load",
    "sema.legend.tepki": "Support reaction",
    "sema.legend.cokme": "Support settlement [mm]",
    "sonuclar.baslik": "Results",
    "sonuclar.yuk_ekleyin": "Add at least one load, or define a support "
                            "settlement, to see results and support reactions.",
    "uyari.cokme_izostatik": "The system is statically determinate (degree of "
                             "indeterminacy 0): a support settlement displaces "
                             "the beam as a rigid body and produces no internal "
                             "forces. Zero moment and shear diagrams are the "
                             "expected behaviour; the deflection diagram shows "
                             "the displacement.",
    "uyari.ea": "The axial system is statically indeterminate (more than one "
                "horizontally restrained support) and the spans have different "
                "sections. The solver assumes equal axial stiffness (EA) in all "
                "spans, so the distribution of horizontal reactions is "
                "approximate. The shape of the axial force diagram and the "
                "vertical results are unaffected.",

    "kart.maks": "Max. {ad} [{birim}]",
    "kart.min_baslik": "Min. {ad} [{birim}]",
    "kart.konum": "@ x = {x:.2f} m",
    "kart.min": "Min. {deger} @ x = {x:.2f} m",
    "kart.maks_alt": "Max. {deger} @ x = {x:.2f} m",
    "buyukluk.moment": "moment",
    "buyukluk.kesme": "shear",
    "buyukluk.sehim": "deflection",
    "buyukluk.normal": "axial force",

    "diyagram.baslik": "Internal Force Diagrams",
    "diyagram.eksen_x": "Position along the beam [m]",
    "diyagram.hepsi_kapali": "All diagrams are turned off — you can enable them "
                             "under **4. Display** in the sidebar. Metrics, "
                             "support reactions and CSV download are unaffected.",
    "panel.normal": "Axial",
    "panel.kesme": "Shear",
    "panel.moment": "Moment",
    "panel.sehim": "Deflection",

    "csv.diyagram_buton": "⬇️ Diagram data (CSV)",
    "csv.diyagram_dosya": "diagram_moment_shear_deflection.csv",
    "csv.normal_buton": "⬇️ Axial force data (CSV)",
    "csv.normal_dosya": "diagram_axial_force.csv",
    "csv.x": "x [m]",
    "csv.moment": "Moment [kNm]",
    "csv.kesme": "Shear [kN]",
    "csv.sehim": "Deflection [mm]",
    "csv.normal": "Axial [kN]",

    "lisans.kaynak": "Source code (AGPL-3.0)",
    "lisans.atif": "Analysis core: PyCBA — © Colin Caprani, AGPL-3.0",
    "lisans.gelistiren": "Developed by",

    "tepki.baslik": "Support reactions",
    "tepki.dugum": "Node",
    "tepki.konum": "Position [m]",
    "tepki.dusey": "Vertical reaction [kN]",
    "tepki.yatay": "Horizontal reaction [kN]",
    "tepki.moment": "Moment reaction [kNm]",
}

METINLER = {"tr": _TR, "en": _EN}


def cevir(dil: str, anahtar: str, **kw) -> str:
    """Katalogdan metni seçilen dilde biçimlendirilmiş olarak döndür.

    Bilinmeyen dil ya da o dilde eksik anahtar Türkçeye düşer.
    """
    sozluk = METINLER.get(dil or VARSAYILAN_DIL, _TR)
    return sozluk.get(anahtar, _TR[anahtar]).format(**kw)
