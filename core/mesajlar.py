"""Çekirdeğin kullanıcıya gösterilebilir mesajları — çok dilli katalog.

`core/` arayüzden bağımsız kalmalı, ama ürettiği doğrulama ve çözüm hataları
doğrudan kullanıcıya gösteriliyor; dolayısıyla dil bilgisi bir yerden gelmek
zorunda. Çözüm: dil, çağıran katmandan **açık parametre** olarak geçirilir
(`validate(dil=...)`, `solve(model, dil=...)`). Modül düzeyinde "geçerli dil"
global'i BİLEREK yoktur: Streamlit her kullanıcı oturumunu ayrı bir iş
parçacığında çalıştırdığı için global, bir kullanıcının dil seçimini diğerine
sızdırırdı.

Varsayılan `tr`; böylece dil geçirmeyen çağrılar (ve testler) eskisi gibi çalışır.
Bilinmeyen anahtar/dil sessizce Türkçeye düşer — eksik çeviri arayüzü kırmaz.
"""

VARSAYILAN_DIL = "tr"

_TR = {
    # --- BeamModel.validate ---
    "aciklik_yok": "En az bir açıklık tanımlanmalı.",
    "aciklik_pozitif": "Tüm açıklık uzunlukları pozitif olmalı.",
    "ei_sayisi": "EI sayısı ({n_ei}) açıklık sayısına ({n_span}) eşit olmalı.",
    "ei_pozitif": "Tüm EI değerleri pozitif olmalı.",
    "mesnet_sayisi": "Mesnet sayısı ({n_sup}) düğüm sayısına "
                     "({n_node} = açıklık + 1) eşit olmalı.",
    "mesnet_tipi": "Bilinmeyen mesnet tipi: {tip!r}",
    "mafsal_dugum_gecersiz": "Mafsal düğüm no {h} geçersiz: yalnız ara düğümlere "
                             "(2..{son}) mafsal konabilir.",
    "mafsal_tekrar": "Düğüm {h} birden fazla kez mafsal olarak verildi.",
    "ic_mafsal_aciklik_gecersiz": "Açıklık içi mafsal: açıklık no {sp} geçersiz "
                                  "(1..{n_span}).",
    "ic_mafsal_konum": "Açıklık {sp} içindeki mafsal konumu a={a:g} m geçersiz: "
                       "0 ile {L:g} m arasında (uçlar hariç) olmalı. "
                       "Mesnet hizasında mafsal için düğüm mafsalını kullanın.",
    "ic_mafsal_tekrar": "Açıklık {sp}, a={a:g} m'de birden fazla mafsal verildi.",
    "yuk_tipi_bilinmeyen": "Yük {i}: bilinmeyen tip {kind!r}",
    "yuk_aciklik_gecersiz": "Yük {i}: açıklık no {sp} geçersiz (1..{n_span}).",
    "yuk_oneki": "Yük {i}: {mesaj}",
    "yuk_parametre_sayisi": "'{kind}' yükü {beklenen} parametre bekler "
                            "({adlar}), {verilen} verildi.",
    # --- check_load_position ---
    "konum_aciklik_disinda": "Konum a={a:g} m açıklık dışında "
                             "(0 ile {L:g} m arasında olmalı).",
    "a_negatif": "Başlangıç konumu a negatif olamaz.",
    "c_pozitif": "Yayılı uzunluk c pozitif olmalı.",
    "c_pozitif_trapez": "Yayılı uzunluk c pozitif olmalı "
                        "(tüm açıklık için a=0, c=0 girin).",
    "yuk_aciligi_asiyor": "Yük açıklığı aşıyor: a+c = {ac:g} m > L = {L:g} m. "
                          "Başlangıç konumunu veya uzunluğu küçültün.",
    # --- solver ---
    "mekanizma": "Sistem kararsız (mekanizma): statik belirsizlik derecesi "
                 "{derece}. {n_mafsal} mafsal için mesnet tepkisi yetersiz — "
                 "mafsal sayısını azaltın ya da mesnet ekleyin/güçlendirin.",
    "cozulemedi": "Sistem çözülemedi: {hata}\nMesnetleri kontrol edin — kiriş "
                  "kararsız (mekanizma) olabilir (örn. tek bir mafsallı mesnet "
                  "yeterli değildir).",
    "tekil_matris": "Sistem kararsız: rijitlik matrisi tekil. "
                    "Mesnetleri kontrol edin.",
    "sonuc_tanimsiz": "Sistem kararsız: sonuçlar sonsuz/tanımsız çıktı. "
                      "Mesnetleri kontrol edin.",
    "eksenel_cozulemedi": "Eksenel sistem çözülemedi: {hata}",
    # --- axial ---
    "eksenel_mesnet_yok": "Eksenel yük var ama yatayda tutulu mesnet yok "
                          "(pin veya fixed gerekli); kiriş eksenel doğrultuda "
                          "mekanizmadır.",
}

_EN = {
    "aciklik_yok": "At least one span must be defined.",
    "aciklik_pozitif": "All span lengths must be positive.",
    "ei_sayisi": "The number of EI values ({n_ei}) must equal the number of "
                 "spans ({n_span}).",
    "ei_pozitif": "All EI values must be positive.",
    "mesnet_sayisi": "The number of supports ({n_sup}) must equal the number of "
                     "nodes ({n_node} = spans + 1).",
    "mesnet_tipi": "Unknown support type: {tip!r}",
    "mafsal_dugum_gecersiz": "Hinge node {h} is invalid: hinges may only be "
                             "placed at interior nodes (2..{son}).",
    "mafsal_tekrar": "Node {h} was given as a hinge more than once.",
    "ic_mafsal_aciklik_gecersiz": "In-span hinge: span number {sp} is invalid "
                                  "(1..{n_span}).",
    "ic_mafsal_konum": "Hinge position a={a:g} m in span {sp} is invalid: it must "
                       "lie between 0 and {L:g} m (ends excluded). For a hinge at "
                       "a support, use a node hinge instead.",
    "ic_mafsal_tekrar": "More than one hinge given in span {sp} at a={a:g} m.",
    "yuk_tipi_bilinmeyen": "Load {i}: unknown type {kind!r}",
    "yuk_aciklik_gecersiz": "Load {i}: span number {sp} is invalid (1..{n_span}).",
    "yuk_oneki": "Load {i}: {mesaj}",
    "yuk_parametre_sayisi": "Load type '{kind}' expects {beklenen} parameters "
                            "({adlar}), but {verilen} were given.",
    "konum_aciklik_disinda": "Position a={a:g} m is outside the span "
                             "(must be between 0 and {L:g} m).",
    "a_negatif": "Start position a cannot be negative.",
    "c_pozitif": "Distributed length c must be positive.",
    "c_pozitif_trapez": "Distributed length c must be positive "
                        "(enter a=0, c=0 to cover the whole span).",
    "yuk_aciligi_asiyor": "Load extends beyond the span: a+c = {ac:g} m > "
                          "L = {L:g} m. Reduce the start position or the length.",
    "mekanizma": "The system is unstable (mechanism): degree of static "
                 "indeterminacy is {derece}. Support reactions are insufficient "
                 "for {n_mafsal} hinge(s) — reduce the number of hinges or "
                 "add/strengthen supports.",
    "cozulemedi": "The system could not be solved: {hata}\nCheck the supports — "
                  "the beam may be unstable (a mechanism); e.g. a single pinned "
                  "support is not enough.",
    "tekil_matris": "The system is unstable: the stiffness matrix is singular. "
                    "Check the supports.",
    "sonuc_tanimsiz": "The system is unstable: results came out infinite/undefined. "
                      "Check the supports.",
    "eksenel_cozulemedi": "The axial system could not be solved: {hata}",
    "eksenel_mesnet_yok": "There is an axial load but no horizontally restrained "
                          "support (pin or fixed is required); the beam is a "
                          "mechanism in the axial direction.",
}

KATALOG = {"tr": _TR, "en": _EN}


def mesaj(anahtar: str, dil: str = None, **kw) -> str:
    """Katalogdan mesajı seçilen dilde biçimlendirilmiş olarak döndür.

    Bilinmeyen dil ya da o dilde eksik anahtar Türkçe metne düşer; çeviri
    eksikliği hiçbir zaman KeyError'a dönüşmez.
    """
    sozluk = KATALOG.get(dil or VARSAYILAN_DIL, _TR)
    return sozluk.get(anahtar, _TR[anahtar]).format(**kw)
