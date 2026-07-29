# PyCBA Web Arayüzü — Uygulama Planı

## Context (Neden bu proje?)

PyCBA güçlü ama **hiçbir grafik arayüzü olmayan** bir Python kütüphanesi: kullanmak için
kod yazmak (`L`, `EI`, `R/supports`, `LM` listeleri) gerekiyor. Bu, Python bilmeyen bir
inşaat mühendisliği öğrencisi için erişilemez kılıyor. Amaç: PyCBA'yı **değiştirmeden**,
onun *üstüne* bir web arayüzü inşa ederek "form doldur → moment/kesme/sehim diyagramı gör"
akışını herkese açmak. İleride (2. aşama) bir kiriş fotoğrafı/krokisi yükleyip modeli
otomatik çıkaran bir katman eklenecek.

**Önemli mimari ilke:** Hesap mantığı arayüzden ayrı tutulacak (`core/` vs `app.py`).
Böylece ileride Streamlit yerine Gradio/Flask'a geçmek yalnızca sunum katmanını değiştirmek
olur — çekirdek kod aynı kalır. (Kullanıcının "arayüzü sonra değiştirebilir miyim?" sorusunun
cevabı: evet, bu ayrım sayesinde.)

**Fork gerekmez.** PyCBA bir bağımlılık olarak `import` edilecek (numpy gibi). Bu yeni,
bağımsız bir proje. Fork yalnızca PyCBA'nın iç kodunu değiştirmek istenirse gerekir.

Bu plan yalnızca **1. Aşama**yı (resimsiz, form-tabanlı çalışan uygulama) kapsar.
2. Aşama (resimden model) ayrıca planlanacak.

## Karar Özeti (kullanıcıdan alınan)
- **UI teknolojisi:** Streamlit (şimdilik; sonra değiştirilebilir — mimari buna hazır)
- **Sıra:** Önce solver UI, resim özelliği sonra

## Ortamın Mevcut Durumu
- Konum: `C:\Users\hreis\Masaüstü\pyCBA` (tüm dosyalar burada; "pyCBA fork" diye ayrı dizin yok)
- `.venv` kurulu; içinde `pycba 1.0.1`, numpy, scipy, matplotlib mevcut
- Örnek dosyalar mevcut: `ornek1_surekli_kiris.py`, `ornek2_diyagram.py`, `ornek3_senin_kirisin.py`
- Eksik: `streamlit` ve `plotly` (kurulacak)

## PyCBA API — Kullanılacak Fonksiyonlar (keşif sonucu)
Kaynak: `.venv/Lib/site-packages/pycba/`
- **Analiz:** `BeamAnalysis(L, EI, R=None, LM=None, supports=None, D=None, eletype=None)`
  → `.analyze()` (`analysis.py:69, :406`)
- **Dostane mesnet girişi:** `supports=["pin","fixed","free",...]` (isimle; `analysis.py:139`,
  sözlük `utils.py:15` `_SUPPORT_DOF`). UI'da dropdown'a birebir uyar.
- **Kompakt metin formatı:** `parse_beam_string("P40R20R")` → `(L, EI, R, eType)`
  (`utils.py:138`). İleride resim→model çıktısı için ideal ara-format; 1. aşamada
  "gelişmiş metin girişi" olarak da sunulabilir.
- **Yük tipleri (LM satırları):** UDL `[span,1,w]`, Tekil `[span,2,P,a]`,
  Kısmi UDL `[span,3,w,a,c]`, Moment `[span,4,M,a]`, Trapez `[span,5,w1,w2(,a,c)]`
  (`analysis.py:106-118`)
- **Sonuçlar:** `ba.beam_results.R` (tepkiler); `ba.beam_results.results.M / .V / .x / .D`
  (`results.py:75, :421`)
- **İnteraktif çizim:** `cba.set_backend("plotly")` → `ba.plot_results()` bir Plotly
  figürü döndürür (`plotting.py:16, 40`; `results.py:921`). Streamlit'te `st.plotly_chart()`
  ile doğrudan gömülür; fareyle değer okuma bedava gelir.

## Yapı (dizin düzeni)
```
pyCBA/                          (mevcut working directory)
├── .venv/                      (mevcut)
├── core/
│   ├── __init__.py
│   ├── model.py                # BeamModel veri sınıfı (L, EI, supports, loads)
│   └── solver.py               # model -> pycba çağrısı -> sonuç sözlüğü (UI'dan bağımsız)
├── app.py                      # Streamlit arayüzü (yalnızca sunum + core çağrıları)
├── requirements.txt            # pycba, streamlit, plotly
└── ornek*.py                   (mevcut örnekler; dokunulmaz)
```

## Uygulama Adımları

### Adım 0 — Bağımlılıklar
- `.venv` içine kur: `streamlit`, `plotly`
- `requirements.txt` oluştur (pycba, streamlit, plotly) — taşınabilirlik için.

### Adım 1 — Çekirdek: `core/model.py`
- Basit bir `BeamModel` veri sınıfı (dataclass): açıklık uzunlukları, her açıklık için
  `EI`, düğüm mesnetleri (isim listesi), yük listesi.
- `to_pycba()` metodu: modeli `BeamAnalysis`'in beklediği `L, EI, supports, LM`
  argümanlarına çevirir. Doğrulama: düğüm sayısı = açıklık+1, mesnet sayısı tutarlı mı.

### Adım 2 — Çekirdek: `core/solver.py`
- `solve(model) -> dict` fonksiyonu: `BeamAnalysis(...).analyze()` çağırır,
  `{R, x, M, V, D, Mmax, Mmin, Vmax, ...}` döndürür. **Streamlit'e hiç bağımlı değil**
  (böylece ileride başka arayüzden de çağrılır, testi kolay).
- Hata yönetimi: kararsız/hesaplanamaz sistemde anlamlı mesaj (PyCBA `ValueError` fırlatır;
  yakalanıp kullanıcıya "sistem kararsız, mesnetleri kontrol edin" olarak iletilir).

### Adım 3 — Arayüz: `app.py` (Streamlit)
- **Girdi paneli (kenar çubuğu):**
  - Açıklık sayısı seçici → her açıklık için uzunluk ve `EI` girişi
  - Her düğüm için mesnet tipi dropdown (pin / roller / fixed / free) — `_SUPPORT_DOF` ile eşleşir
  - Yük ekleme tablosu: tip (UDL/tekil/kısmi/moment) + değer + konum
- **Sonuç paneli (ana alan):**
  - `set_backend("plotly")` + `plot_results()` → `st.plotly_chart()` ile interaktif diyagram
  - Özet metrikler: max/min moment, max kesme, mesnet tepkileri (`st.metric` / tablo)
- **Durum yönetimi:** `st.session_state` ile girilen model korunur (yeniden çizimde kaybolmaz).

### Adım 4 — Doğrulama (aşağıdaki bölüm)

## 2. Aşama (SONRA — bu planın kapsamı dışında, not olarak)
Resim→model: `app.py`'ye bir `st.file_uploader` + "modeli çıkar" düğmesi. Görüntüyü bir
LLM'e (Claude API) gönderip `parse_beam_string` uyumlu bir çıktı / JSON model alır, formu
**ön-doldurur**, kullanıcı **onaylar/düzeltir**, sonra çözer. Deterministik çekirdek (core/)
hiç değişmez; yalnızca yeni bir "giriş kaynağı" eklenir. API anahtarı/maliyet kararı o
aşamada verilecek.

## Doğrulama (uçtan uca test)
1. `.venv` ile `streamlit run app.py` çalışır, tarayıcıda açılır.
2. **Referans problem:** 2×6 m sürekli kiriş, tüm açıklıklarda 20 kN/m UDL, 3 mafsal mesnet.
   Beklenen (zaten `ornek1` ile doğrulandı): M_B = −90 kN·m, tepkiler 45/150/45 kN.
   Arayüzde aynı değerler çıkmalı.
3. Bir tekil yük ve bir ankastre mesnet senaryosu ekleyip diyagramın mantıklı değiştiği
   gözlenir (ankastre uçta sıfır-olmayan moment).
4. `core/solver.py` doğrudan Python'dan çağrılıp (UI'sız) aynı sonucu verdiği kontrol edilir
   — arayüz/çekirdek ayrımının çalıştığının kanıtı.
5. Kararsız sistem (ör. tek mafsal) girilip anlamlı hata mesajı gösterildiği doğrulanır.

---

# Yük Düzenleri / Zarf Diyagramları — Plan (2026-07-29)

Bir sonraki iş kalemi. Kararlar kullanıcıyla birlikte alındı; kodlama başlamadan
önce buradaki tespitleri okuyun — ikisi ölçümle bulundu, tahminle değil.

## Neden gerekli

Hareketli yük her açıklıkta aynı anda durmak zorunda değildir; **hiçbir tek
yükleme her kesitte yönetici olmaz**. 2×6 m, 20 kN/m ile ölçüldü:

| Yükleme | Açıklık momenti (x=2.25) | Mesnet momenti M_B |
|---|---|---|
| İki açıklık da yüklü | 50.62 | **−90.00** |
| Yalnız 1. açıklık | **67.72** | −45.00 |
| Yalnız 2. açıklık | −17.10 | −45.00 |

Açıklık momentinin gerçek maksimumu 68.90 kNm (x=2.625, yalnız 1. açıklık) —
"hepsi yüklü" varsayan biri %36 eksik görür. Ayrıca 2. açıklık tek başına
yüklüyken **R_A = −7.50 kN**, yani mesnet kalkıyor; ankraj gerektiren bu durum
da ancak zarfla görünür.

## Tespit 1 — zarfı KENDİMİZ hesaplıyoruz (PyCBA `LoadPattern` kullanılmıyor)

Düzenleri kullanıcının açıklıkları üzerinde üretip her birini kendi `solve()`
çağrımızla çözmek, PyCBA'nın `LoadPattern`'iyle **birebir aynı** M/V zarfını
veriyor (tek fark: aşağıdaki sıfır kenetleme). Kendi hesabımızın üstünlükleri:

- **Sehim zarfı** elde ediliyor — PyCBA `Envelopes` yalnız M, V ve tepki taşır.
- Tepki zarfı doğrudan **kullanıcı düğüm numarasıyla** çıkar; PyCBA'nın kompakt
  DOF vektörünü (`Rmaxval`) mesnet tiplerine bakarak eşlemek gerekmez.
- Düzen adları kendi TR/EN kataloğumuzdan gelir.
- **Gerber uyumu:** PyCBA patternlemeyi GENİŞLETİLMİŞ açıklıklara uygular.
  2 açıklıklı bir kirişe açıklık içi mafsal konunca 3 açıklık görüp 5 düzen
  üretiyor ve "tek/çift açıklıklar" kullanıcının numaralandırmasıyla örtüşmüyor
  (ölçüldü). Kendi hesabımızda düzenler kullanıcının açıklıklarında kurulur,
  genişletme her düzenin içinde `solve()` tarafından yapılır.

Maliyet: N+2 kez `solve()`, her biri ~10 ms. Düzen kuralları standardın,
PyCBA'nın değil; `pattern.py:151-190` referans olarak okunabilir.

## Tespit 2 — PyCBA zarfı SIFIRA KENETLER (bu davranış korunacak)

`results.py:468` zarf dizilerini sıfırla başlatıp yalnız üzerine yazıyor, yani
`Mmax >= 0` ve `Mmin <= 0` her zaman. Mesnet üstünde tüm düzenlerde moment
negatifse:

```
x=6 m, düzenlerin momentleri: [-189.0, -139.5, -139.5, -189.0]
  PyCBA:  Mmax = 0.0       <- eksene kenetli
  ham:    Mmax = -139.5    <- gerçek en büyük
```

**KARAR: PyCBA geleneği korunur** (zarf ekseni sarar). Zarf dizileri sıfırla
başlatılıp `np.maximum` / `np.minimum` ile güncellenir.

## Alınan kararlar

1. **Sıfır kenetleme:** PyCBA geleneği (yukarıdaki).
2. **Yük sınıfı varsayılanı:** `G` (sabit) — mevcut modeller ve testler değişmez.
3. **Yerleşim:** mevcut "Sonuçlar" bölümü değişmez; zarf **ayrı başlık** altında
   onun altında durur (sekme değil — ikisi de aynı anda görünür kalsın).
4. **Katsayı varsayılanı:** Eurocode; panelden değiştirilebilir, yönetmelik
   seçimi açıkça yazılır.

## Katsayı setleri

Panelde `selectbox` (Eurocode / TS 500 / Özel) + 4 `number_input`. Seçime göre
dolar; elle değiştirilince seçim "Özel"e döner. Hangi kombinasyonun kurulduğu
caption ile yazılır ("1.35G + 1.5Q / 1.0G").

| | γ_G,maks | γ_G,min | γ_Q,maks | γ_Q,min |
|---|---|---|---|---|
| Eurocode (EN 1990, 6.10 STR) | 1.35 | 1.00 | 1.50 | 0 |
| TS 500 (6.2.6) | 1.40 | 0.90 | 1.60 | 0 |

**Bu değerler yönetmelik metnine karşı teyit edilmeli** (çevrimdışı doğrulanamadı).

## Yapılacaklar

**`core/model.py`**
- `Load.sinif: str = "G"` (`"G"` sabit / `"Q"` hareketli); `validate()` denetler.
- Eksenel yükler patternlenmez, hep G sayılır (düşey düzenlemenin konusu değil).

**`core/zarf.py` (yeni)**
- `KATSAYI_SETLERI = {"eurocode": (1.35, 1.00, 1.50, 0.00), "ts500": (1.40, 0.90, 1.60, 0.00)}`
- `duzenler(n_span)` → mesnet başına komşu-iki-açıklık (n−1) + tek + çift + tümü.
- `solve_envelope(model, katsayilar, dil) -> dict`: her düzende yükleri
  G/Q ve γ'lara göre ölçekle → `solve()` → M/V/D için sıfırdan başlayan
  pointwise max/min, tepkiler düğüm bazında, eş zamanlı etkiler (Vco_Mmax vb.)
  argmax indisinden, her ekstremde "yöneten düzen".

**`core/mesajlar.py`** — tanımsız yük sınıfı; hareketli yük yokken uyarı
(hata değil, zarf tek düzene iner).

**`app.py`**
- Yük ekleme ve düzenleme formlarına yük sınıfı seçimi.
- Kenar çubuğunda "5. Yük düzenleri": hesapla anahtarı, yönetmelik seçimi,
  4 katsayı alanı. (Kenar çubuğunda `st.rerun()` çağırma — bkz. CLAUDE.md.)
- Ayrı "Zarf diyagramları" bölümü: metrik kartları (caption'da yöneten düzen),
  Plotly figürü (kesme/moment/sehim, iki eğri + taralı bant, `fill="tonexty"`),
  tepki tablosu (düğüm başına maks/min), ayrı CSV.

**`ui_dil.py`** — TR/EN: bölüm başlıkları, yük sınıfı adları, yönetmelik adları,
düzen adları (`duzen.mesnet_negatif`, `duzen.tek`, `duzen.cift`, `duzen.tum`),
panel/sütun/CSV başlıkları.

**Testler**
- Analitik: 2×6 m, G=20/Q=10, γ=1 → açıklık maksimumu 68.90 ("yalnız 1. açıklık"),
  mesnet minimumu −90 ("tüm açıklıklar"); zarf ikisini de yakalamalı.
- Çapraz doğrulama: kendi zarfımız PyCBA `LoadPattern` ile aynı (prototipte geçti).
- Gerber: açıklık içi mafsallı modelde düzen sayısı KULLANICI açıklığına göre.
- Çökme her düzende korunmalı (`build_pycba_model` prescribed displacement'ı
  taşıyor; çökme kalıcı etkidir, patternlenmez).
