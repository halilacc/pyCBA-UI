# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proje

PyCBA (sürekli kiriş analizi kütüphanesi) üzerine kurulmuş Streamlit web arayüzü.
PyCBA fork edilmez, `.venv` içinden bağımlılık olarak `import` edilir. Git deposu değildir.
Tüm **kod/yorum/docstring** dili Türkçe; buna uy. Kullanıcıya görünen metinler ise
Türkçe+İngilizce kataloglardadır (bkz. "Dil"). Detaylı tasarım kararları
`pyCBA-UI-Planı.md`'de; o dosya depoda izlenmez, yalnızca yerelde durur.

## Komutlar

```powershell
# Uygulamayı çalıştır (sargısız — streamlit.exe kullanma, aşağıya bak)
.venv\Scripts\python.exe -m streamlit run app.py

# Bağımlılıklar (dev = pytest dahil; requirements.txt Cloud'un kurduğudur)
.venv\Scripts\pip.exe install -r requirements-dev.txt

# Testler — çekirdek değişikliğinden sonra ÇALIŞTIR
.venv\Scripts\python.exe -m pytest -q

# Çekirdeği elle gözlemle (referans problemin ayrıntılı çıktısı)
.venv\Scripts\python.exe ornek1_surekli_kiris.py
```

Sistem Python'u değil, her zaman `.venv\Scripts\python.exe` kullanılır.

**Streamlit yeniden başlatma (Windows tuzağı):** Arka plandaki `streamlit.exe`'yi
durdurmak asıl python alt sürecini öldürmez; port yetim süreçte kalır ve bayat modül
hataları üretir. Yeniden başlatmadan önce
`Get-NetTCPConnection -LocalPort <port> -State Listen` ile PID'yi bulup
`Stop-Process -Id <pid> -Force` ile öldür. Bu yüzden başlatırken `python -m streamlit`
tercih edilir.

**Referans problem:** 2×6 m sürekli kiriş, her açıklıkta 20 kN/m UDL, 3 mafsal →
M_B = −90 kNm, tepkiler 45/150/45 kN (`ornek1_surekli_kiris.py`). Çekirdek
değişikliklerinden sonra bu değerlerin korunduğunu kontrol et.

**Testler:** `tests/test_core.py` — hepsi elle/kapalı formülle doğrulanabilir
vakalar (referans problem, basit kiriş, konsol, Gerber düzenleri, mekanizma
hatası, eksenel/normal kuvvet). PyCBA çıktısını "olduğu gibi" dondurma; yeni test
eklerken de analitik olarak doğrulanabilir bir vaka seç. `tests/test_dil.py` iki
dil kataloğunun bütünlüğünü denetler. `tests/test_arayuz.py` `AppTest` ile
`app.py`'yi gerçekten çalıştırır (sunum katmanı regresyonları). Kök
`conftest.py` yalnızca proje kökünü `sys.path`'e sokmak içindir.

**Arayüzü tarayıcısız sınama:** `streamlit.testing.v1.AppTest` `app.py`'yi
gerçekten çalıştırır ve istisnaları yüzeye çıkarır — sunum katmanındaki bir
değişikliği doğrulamanın en hızlı yolu:
`at = AppTest.from_file("app.py"); at.session_state["dil"] = "en"; at.run()`
sonra `at.exception`, `at.metric`, `at.error`, `at.sidebar.header` incelenir.
Plotly figürü de denetlenebilir: `json.loads(at.get("plotly_chart")[i].proto.spec)`
— `.figure` özniteliği YOKTUR ve `y` dizileri ikili (typed array) gelir; iz
adı/dolgusu/ekseni okunabilir, sayısal değerler için çekirdeğe bak.

## Mimari

Temel ilke: **hesap mantığı arayüzden tamamen ayrı.** `core/` Streamlit'e hiç bağımlı
değildir; arayüz ileride Gradio/Flask ile değiştirilebilmelidir. UI mantığını asla
`core/`e, hesap mantığını asla `app.py`'ye koyma.

- `core/model.py` — `BeamModel` ve `Load` dataclass'ları, doğrulama (`validate()` hata
  mesajı listesi döndürür), PyCBA argümanlarına çeviri (`to_pycba()`). `LOAD_TYPES`
  sözlüğü yük tipi → PyCBA LM kodu + parametre adları eşlemesinin tek kaynağıdır;
  yeni yük tipi eklemek çoğunlukla buraya, `ui_dil.py`'ye (`yuk.<kind>`,
  `ipucu.<kind>`, gerekiyorsa `param.<p>` — iki dile de) ve `app.PARAM_UNITS`'a
  satır eklemektir. `hinges` (Gerber iç mafsalları, 1-tabanlı ara
  düğüm no'ları) → `eletypes()` ile PyCBA `eletype` koduna çevrilir; kural: mafsal
  her zaman SAĞDAKİ elemanın sol ucuna verilir (açıklık i ↔ düğüm i), böylece her
  açıklık ya FF(1) ya PF(3) olur. `static_degree()` = r − h − 2 ile mekanizma
  ön-kontrolü yapılır (solver bunu kullanır).
  `span_hinges` = açıklık İÇİNDE mafsal (açıklık no, sol uçtan a) → `expand()`
  açıklığı böler, araya `free` düğüm koyar, yükleri alt açıklıklara dağıtır
  (`_split_load`; kısmi UDL/trapez kesimi aşarsa bölünür, trapezde şiddet
  interpolasyonla bulunur) ve `node_map` döndürür. **Çözüm/çizim hep genişletilmiş
  model üzerinden yapılır**; `solve()` tepkilerde `node`u kullanıcı numarasına geri
  çevirir, çizim `node_expanded`i kullanır. Bu ayrımı bozma.
  `springs` = elastik yay mesnet `{düğüm no: k [kN/m]}`; ilgili düğümün tipi
  `"spring"` olmak ZORUNDA (ikisi birlikte doğrulanır). Yay varken `to_pycba`
  dostane `supports=` yolunu bırakıp ham `R` vektörü kurar — PyCBA'da yay
  yalnız `R` ile verilir ve ikisi bir arada geçilemez (`analysis.py:95-103,152`).
  Yay yoksa eski yol aynen korunur. `"spring"` adı PyCBA'nın çizici glif
  sabitiyle birebir aynıdır (`render.py:41`), şema bedavaya doğru çizilir.
  Yay `static_degree()`de tepki bileşeni sayılır (r += 1); `expand()` yay
  katsayılarını da yeni numaralandırmaya taşır. Dönme yayı yoktur (PyCBA
  destekler, arayüz düşeyle sınırlı).
  `settlements` = mesnet çökmesi `{düğüm no: düşey yer değiştirme [m]}` →
  `to_pycba` bunu PyCBA'nın öngörülmüş yer değiştirme vektörüne (`D=`, düğüm
  başına düşey+dönme, bilinmeyende `None`) çevirir; yalnız düşey DOF yazılır.
  İşaret sehim `D` ile aynıdır (**aşağı negatif**); arayüz "çökme"yi pozitif
  sorup `app.py`'de tek satırda mm→m + işaret çevirir. Yalnız mesnetli düğüme
  verilebilir (serbest düğümde doğan kuvvet PyCBA'nın tepki vektörüne girmez,
  sessizce kaybolurdu). `expand()` çökmeleri de yeni numaralandırmaya taşır.
- `core/solver.py` — `solve(model) -> dict` (diyagram dizileri, ekstremler, tepkiler,
  `analysis` nesnesi). Kararsız sistemde kullanıcıya gösterilebilir `SolverError`
  fırlatır. `_map_reactions` PyCBA'nın kompakt tepki vektörünü (yalnızca tutulu DOF'lar,
  düğüm başına düşey+dönme sırasıyla) mesnet tiplerine bakarak düğümlere eşler.
  **Yay mesnetler `R`de HİÇ GEÇMEZ**: PyCBA yay kuvvetini ayrı `Rs` vektöründe
  verir (`-k·u`, yukarı pozitif; `analysis._reactions`). İki vektör ayrı ayrı
  ilerletilir — yayı `R`den okumaya çalışmak sonraki BÜTÜN tepkileri kaydırır.
  `build_beam(model)` analiz çalıştırmadan şema çizimi için `pycba.Beam` verir.
  Sehim dizisi `res.D`den DEĞİL `_sehim_dizisi(vRes)`ten kurulur: PyCBA eleman
  dizilerinin ilk/son (tekrarlanan) dolgu istasyonlarına sehim yazmaz, 0 bırakır
  — mesnette görünmez ama çöken mesnette ve açıklık içi mafsalın serbest
  düğümünde eğri oraya "düşer". PyCBA kendi çiziminde `m.D[1:-1]` ile atar.
- `app.py` — yalnızca sunum: sidebar'da girdi, `st.session_state.loads` içinde yük
  listesi, sonuçlar Plotly ile (`plot_results(backend="plotly")`).

PyCBA API referansı (LM satır formatları, `supports=` adları, sonuç erişimi) plan
dosyasının "PyCBA API" bölümünde satır numaralarıyla belgelidir; kaynak
`.venv/Lib/site-packages/pycba/`. **Plan dosyası depoda İZLENMEZ** (bkz.
`.gitignore`) — dışarıdan gelen bir katkıcı ona ulaşamaz; ona hitap eden bir
açıklama yazarken referansı plan dosyasına değil doğrudan PyCBA kaynağına ver.

Dikkat edilecekler:
- `Load.span` 1-tabanlıdır; `a` konumu her zaman açıklığın **sol ucundan** ölçülür.
- Trapez yükte `a=0, c=0` "tüm açıklık" demektir; `to_lm_row` bu durumda a/c'yi düşürür.
- `app.py`'deki konum girdilerinin `key`'i açıklık no ve L'ye bağlıdır — açıklık
  değişince bayat değer taşınmasın diye; bu deseni bozma.
- **Kenar çubuğunda `st.rerun()` çağırma** — `yeniden_calistir = True` kur, blok
  sonunda tek noktadan tetiklenir. Streamlit bir çalıştırmada ÇİZİLMEYEN
  widget'ın durumunu siler; ekleme/silme bloğunda anında rerun edilince betik
  orada kesilir, ondan sonraki widget'lar (çökme alanları, "4. Görünüm"
  anahtarları) çizilmez ve bir sonraki çalıştırmada VARSAYILANLARIYLA geri
  gelirdi (sehim grafiğini kapatıp yük ekleyince grafik yeniden açılıyordu).
  Ana alandaki rerun'lar kenar çubuğundan sonra çalıştığı için serbesttir.
  Muhafızı: `tests/test_arayuz.py`.
- Sehim `D` metre cinsindendir; UI mm'ye çevirerek gösterir. Mesnet çökmesi de
  öyle: çekirdek m, arayüz mm.
- **Diyagram ızgarası `solver.ISTASYON_SAYISI` (=1000) ile kurulur.** PyCBA
  varsayılanı 100'dür ve ızgara eşit aralıklıdır — yük süreksizliklerine
  istasyon EKLENMEZ (`results.py`: `xr = dx * np.arange(0, npts + 1)`). Tepe
  değer iki istasyon arasına düşerse ekstrem düşük okunur; 100'de L=6 m'de
  a=2 m'deki P=100 kN için M_maks 133.33 yerine 132.00 çıkıyordu (%1). Sayıyı
  DÜŞÜRME; muhafızı `tests/test_core.py::test_tekil_yuk_tepe_degeri_izgaradan_kacmaz`.
  Artık hata tam sıfırlanmaz (yük konumu ızgaraya denk gelmedikçe) — README
  "Bilinen sınırlar"da yazılı.
- **Şema figürü `matplotlib.figure.Figure` ile kurulur, `plt.subplots()` ile
  DEĞİL** (`app.py:_sema_ciz`). pyplot figürleri global bir kayıtta tutar,
  Streamlit ise her oturumu ayrı iş parçacığında çalıştırır; global kayıt çok
  kullanıcılı sunucuda yarışa açıktır. `Figure` doğrudan kurulunca `plt.close()`
  de gerekmez. Testlerde `plt.subplots()` sorun değil (tek iş parçacığı).
- **PyCBA'nın M/V dizilerinde eleman uçları eksene KAPANIR:** her elemanın ilk ve
  son istasyonu tekrarlanır ve oraya 0 yazılır, yani ara mesnette M dizisinde iki
  sıfır bulunur. Artefakt gibi görünür ama bilinçli çizim geleneğidir — PyCBA
  bunu `results.py:329`da (`deflection_curve` docstring'i) "diyagram eksene
  kapansın diye" diye açıklar. DÜZELTMEYE KALKMA. Aynı dolgu SEHİMDE yanlıştır;
  orası `solver._sehim_dizisi` ile onarılır (PyCBA da kendi çiziminde atar).
- **Şemada EI'nin görsel karşılığı YOKTUR** (bilerek): `ciz_sema` çiziciye
  EI'leri eşitlenmiş bir kopya verir. PyCBA açıklıkların EI'si farklı olunca
  kirişi derinliği EI^(1/3) ile değişen gri gövde olarak çiziyor; gövde ara
  mesnet gliflerini, düğüm harflerini ve çökme etiketlerini yutuyordu. Hesap
  gerçek EI ile yapılır. Muhafızı: `tests/test_arayuz.py` (piksel karşılaştırma).
- **Şema ölçeği içerikten bağımsızdır** (`ui_cizim._sabitle_olcek`): kutu
  genişliği `SEMA_KUTU_ORANI` ile sabitlenir, figür YÜKSEKLİĞİ veri
  en-boyundan türetilir — `app.py` figür boyu vermeye çalışmasın. PyCBA
  `adjustable="box"` kullandığı için düşey veri aralığı (tekil yük oku, yukarı
  yük, moment yayı, tepki okları) kutuyu daraltıyor, punto cinsinden sabit
  yazı/çizgi çizime göre 1.8 kata varan oranda büyüyüp küçülüyordu.
  `ax.get_position()` varsayılanı AKTİF (daraltılmış) kutudur; dikey pay için
  `original=True` şart, yoksa hesap kendi kendini doğrulayan sabit noktaya
  düşer ve hiçbir şey değişmez.
- Yay mesnede ÇÖKME verilemez (doğrulama reddeder): PyCBA'da öngörülmüş yer
  değiştirme o DOF'un satır/sütununu sıfırlar (`analysis._apply_bc`), yani yay
  rijitliği devre dışı kalır ve düğüm "çöken ankastre" gibi davranır —
  kullanıcının kastettiği (yayın zemin ucunun oturması, kuvvetin k·(u−Δ)
  olması) bu değildir. `app.py` çökme listesinde yay düğümlerini hiç göstermez.
- Çökme İZOSTATİK sistemde kesit tesiri üretmez (yalnız rijit yer değiştirme);
  `app.py` bunu `static_degree() == 0` iken `st.info` ile söyler — sıfır M/V
  "hesap çalışmadı" diye okunmasın.

## Dil (TR/EN)

İki katalog var, ikisi de Streamlit'ten bağımsız saf sözlük:

- `ui_dil.py` — arayüz metinleri (`cevir(dil, anahtar, **kw)`). `app.py` bunu
  `t(...)` adıyla kendine bağlar; `ui_cizim.py` `dil` parametresi alır.
- `core/mesajlar.py` — çekirdeğin kullanıcıya gösterilen hata mesajları
  (`mesaj(anahtar, dil, **kw)`).

Dil, çağıran katmandan **açık parametre** olarak geçer: `validate(dil)`,
`check_load_position(..., dil)`, `solve(model, dil)`, `solve_axial(model, dil)`,
`ciz_sema(..., dil)`. Modül düzeyinde "geçerli dil" global'i BİLEREK yok —
Streamlit her oturumu ayrı iş parçacığında çalıştırdığı için global, bir
kullanıcının seçimini diğerine sızdırırdı. Hepsinin varsayılanı `tr`, yani dil
geçirmeyen çağrılar ve testler eskisi gibi çalışır.

Kural: `app.py`/`ui_cizim.py` içine kullanıcıya görünen sabit dize YAZMA;
anahtar ekle. Anahtarlar nokta ile gruplanır (`mesnet.pin`, `yuk.udl`,
`ipucu.udl`, `param.w`). Birimler (kN, m, kNm²) çeviriye girmez —
`app.PARAM_UNITS` dilden bağımsızdır.

Yeni yük tipi / mesnet tipi eklerken `ui_dil.py`'ye `yuk.<kind>` + `ipucu.<kind>`
(veya `mesnet.<tip>`) satırlarını **iki dile de** ekle; bu anahtarlar kod içinde
dize birleştirmesiyle kurulduğu için aramada görünmez, unutulursa yalnız
`tests/test_dil.py` yakalar. O dosya ayrıca iki dilin anahtar kümesinin ve
`{alan}` adlarının eşleştiğini denetler (uyuşmazlık çalışma zamanında KeyError
olurdu).

## Gece modu (ui_tema.py)

**Karar (2026-07-25):** Streamlit'in kendi `[theme.dark]` tabanına GEÇİLMEDİ.
Geçiş teknik olarak mümkün (1.59 `[theme.light]`/`[theme.dark]`/`theme.dark.sidebar`
destekliyor) ve `_GECE_CSS`'i tamamen silerdi; ama Streamlit'in teması Python'dan
değiştirilemiyor (`st.context.theme.type` salt-okunur), yani kenar çubuğundaki
"🌙 Gece modu" anahtarı kaybolur ve kullanıcı ⋮ → Settings → Appearance'a mahkûm
kalırdı. Anahtarın keşfedilebilirliği tercih edildi. Bu kararı tekrar açmadan
`_GECE_CSS`'i kaldırma.

Bedeli: `config.toml` `base = "light"` olduğu için Streamlit TÜM widget'ları açık
temayla üretir; her yeni widget türü gece modunda beyaz kalabilir. Yeni bir widget
eklerken gece modunu **gözle değil, tarayarak** doğrula — sayfayı gece modunda aç,
konsolda:

```js
function lum(c){const m=c.match(/[\d.]+/g);if(!m||(m[3]!==undefined&&+m[3]<0.5))return -1;
  return (+m[0]*0.299+ +m[1]*0.587+ +m[2]*0.114);}
[...document.querySelectorAll('[data-testid="stSidebar"] *')].flatMap(e=>{
  const s=getComputedStyle(e), r=[];
  if(lum(s.backgroundColor)>150) r.push(['ACIK-ZEMIN',e.dataset.testid,s.backgroundColor]);
  else if(lum(s.color)>=0&&lum(s.color)<90&&(e.innerText||'').trim()&&!e.children.length)
    r.push(['KOYU-YAZI',e.dataset.testid,s.color]);
  return r;});
```

Açık tema değerleri (bunları görürsen kural eksik): zemin `#FBFBFA` / `#F3F2EF`,
metin `#1C1B19` veya `rgba(28,27,25,0.6)`.

Taramanın **yanlış pozitifleri** (düzeltmeye kalkma, ölçüp doğrula):
- `stCheckbox` içindeki 12×12 topuz açık olmalı (mor ray üzerinde).
- `stSidebarCollapseButton` / `stExpandSidebarButton` / `stMainMenuButton`
  ikonları koyu ÖLÇÜLÜR ama ekranda açıktır: bunlara `filter: invert(1)`
  uygulanır, `getComputedStyle` filtre öncesi rengi bildirir.
- Butonlar geçici olarak açık ölçülebilir (hover/rerun anı). Fare müdahalesi
  olmadan, ilgili expander açıkken yeniden ölç.

**Tarayıcı eklentisi yoksa** (Claude in Chrome bağlanmıyorsa) ölçümü headless
Chrome + CDP ile yap; venv'de `websockets` + `requests` zaten var:
`chrome.exe --headless=new --remote-debugging-port=9333 --user-data-dir=… URL`
→ `GET /json` ile `webSocketDebuggerUrl` → `Runtime.evaluate` ile
`getComputedStyle` oku. Açılır listeler `element.click()` ile AÇILMAZ (react-aria
gerçek fare olayı bekler); `Input.dispatchMouseEvent` ile `mousePressed` +
`mouseReleased` gönder.

Yaşanmış tuzaklar — tahmin etme, DOM'dan `getComputedStyle` ile ölç:
- Form gönder butonunda `kind` değeri `secondary` DEĞİL, **`secondaryFormSubmit`**.
- Açılır listeler portal ile `<body>` altına basılır; app kapsayıcısını hedefleyen
  kurallar ulaşmaz (`[data-baseweb="popover"]`, `stSelectboxVirtualDropdown`).
- Selectbox seçenekleri `<li>` DEĞİL: 1.59'da sanal liste react-aria ile çizilir,
  her seçenek `role="option"` taşıyan bir `<div>`'dir. Yalnız `li` hedefleyen
  kural hiç tutmaz. Multiselect HÂLÂ `<li>` kullanır — ikisini de hedefle.
- Multiselect'in "Choose options" ipucu input placeholder'ı değil, ayrı bir `<div>`.
- `number_input` adım ikonlarının rengi SATIR İÇİ verilir; devre dışıyken açık
  temanın `fadedText40`'ı olur (alan boşken −/+ kaybolur).
- İkon SVG'lerine `* { fill: currentColor !important }` YAZMA: Streamlit ikonları
  şeklin önüne `fill="none"` olan 24×24 hizalama path'i koyar; `!important` onu
  da ezip ikonu içi dolu kareye çevirir (temizle ⊗ düğmesinde yaşandı). Gerekirse
  `path:not([fill="none"])` ile kapsamı daralt. Selectbox açılır oku (∨) da aynı
  yapıda — kutunun İÇİNDE, `aria-label="Open"` sarmalayıcısında durur ve genel
  metin kurallarının kapsamına girmez.
- `filter: invert(1)` AİLESİ yalnız ikon içindir (`stSidebarCollapseButton`,
  `stExpandSidebarButton`, `stMainMenuButton`). Metin taşıyan bir öğeyi (örn.
  `stAppDeployButton`) bu listeye EKLEME: zemini de döner, açık bir kutuya
  dönüşür. Ters çevrilen bir öğeye ayrıca açık renk vermek de onu tekrar
  koyulaştırır — ikisi bir arada kullanılmaz.
- Emotion sınıfları (`st-emotion-cache-…`, `st-cm`) sürümle değişir; asla seçici
  olarak kullanma — testid/baseweb/öznitelik yolu kullan.
- `ui_tema.py` içe aktarılmış modüldür: değiştirince Streamlit'i **yeniden başlat**,
  yalnız sayfayı yenilemek yetmez.

## 2. Aşama (henüz yok)

Kiriş fotoğrafından model çıkarma (LLM ile) planlanıyor; formu ön-dolduracak, `core/`
değişmeyecek. Ayrıntı yerel plan dosyasında.
