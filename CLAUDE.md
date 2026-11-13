# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proje

PyCBA (sürekli kiriş analizi kütüphanesi) üzerine kurulmuş web arayüzü:
FastAPI (`api/`) + Next.js (`web/`). PyCBA fork edilmez, `.venv` içinden bağımlılık
olarak `import` edilir. Eski Streamlit arayüzü 2026-11-13'te SİLİNDİ (yerine bu
yığın geçti; geri getirme).
Tüm **kod/yorum/docstring** dili Türkçe; buna uy. Kullanıcıya görünen metinler
Türkçe+İngilizce kataloglardadır (bkz. "Dil"). `pyCBA-UI-Planı.md` yerelde durur,
depoda izlenmez.

## Komutlar

```powershell
# API (sistem Python'u değil, her zaman .venv)
.venv\Scripts\python.exe -m uvicorn api.index:app --port 8000

# Ön yüz (/api/* -> 127.0.0.1:8000; API_URL ile değişir)
cd web; npm run dev

# Bağımlılıklar (dev = pytest + httpx dahil)
.venv\Scripts\pip.exe install -r requirements-dev.txt

# Testler — çekirdek/API değişikliğinden sonra ÇALIŞTIR
.venv\Scripts\python.exe -m pytest -q

# Ön yüz tip denetimi + derleme
cd web; npx next build

# Çekirdeği elle gözlemle (referans problemin ayrıntılı çıktısı)
.venv\Scripts\python.exe ornek1_surekli_kiris.py
```

**Sunucuyu kapatma (Windows tuzağı):** arka plandaki süreç yetim kalabilir; portu
`Get-NetTCPConnection -LocalPort <port> -State Listen` ile bulup
`Stop-Process -Id <pid> -Force` ile öldür.

**Referans problem:** 2×6 m sürekli kiriş, her açıklıkta 20 kN/m UDL, 3 mafsal →
M_B = −90 kNm, tepkiler 45/150/45 kN. Çekirdek değişikliklerinden sonra bu
değerlerin korunduğunu kontrol et (`test_api.py` da bunu sınar).

**Testler:** `tests/test_core.py` — elle/kapalı formülle doğrulanabilir vakalar
(referans, basit kiriş, konsol, Gerber, mekanizma, eksenel). PyCBA çıktısını
"olduğu gibi" dondurma; yeni test de analitik doğrulanabilir olsun.
`tests/test_dil.py` iki kataloğun bütünlüğünü, `tests/test_api.py` HTTP
sözleşmesini (FastAPI `TestClient`), `tests/test_sema.py` şema çizimini
(harflenme, ölçek, EI bağımsızlığı) denetler. Kök `conftest.py` yalnızca proje
kökünü `sys.path`'e sokar.

## Mimari

Üç katman; **hesap mantığı arayüzden tamamen ayrı.** UI mantığını `core/`e, hesap
mantığını `api/` veya `web/`e koyma.

- `core/` — web çerçevesine hiç bağımlı değil (aşağıda ayrıntı).
- `api/index.py` — FastAPI taşıma katmanı. `GET /api/meta` (yük/mesnet tipleri,
  birimler, `ui_dil.METINLER` — metinler tek kaynaktan ön yüze gider, kopyalanmaz)
  ve `POST /api/analiz` (doğrula + çöz + şema SVG). Hata 200 + `hatalar` listesi;
  çözülemese de şema gelir. Çökme API'de mm/aşağı-pozitif; m/core işaretine çeviri
  `modeli_kur`da TEK yerde.
- `ui_cizim.py` — şema çizimi (matplotlib), `ui_dil.py` — arayüz metin kataloğu.
  İkisi de web çerçevesinden bağımsız.
- `web/` — Next.js (App Router, TS) tek sayfa. Plotly diyagramları
  `components/Diyagram.tsx`: moment ekseni ters (sagging aşağıda), mesnet çizgileri
  harfli, ekstrem işaretleri. Şema sunucunun SVG'sidir; gece modunda CSS
  `invert+hue-rotate`. Sayı biçimi: binlik SI dar boşluk (U+202F), ondalık nokta.

### core

- `core/model.py` — `BeamModel` ve `Load` dataclass'ları, doğrulama (`validate()`
  hata listesi döndürür), PyCBA argümanlarına çeviri (`to_pycba()`). `LOAD_TYPES`
  yük tipi → PyCBA LM kodu + parametre adları eşlemesinin tek kaynağıdır; yeni yük
  tipi eklemek çoğunlukla buraya, `ui_dil.py`'ye (`yuk.<kind>`, `ipucu.<kind>`,
  gerekirse `param.<p>`, iki dile de) ve `api/index.PARAM_UNITS`'a satır eklemektir.
  `hinges` (Gerber iç mafsalları, 1-tabanlı ara düğüm no'ları) → `eletypes()` ile
  PyCBA `eletype` koduna: mafsal her zaman SAĞDAKİ elemanın sol ucuna verilir
  (açıklık i ↔ düğüm i). `static_degree()` = r − h − 2 ile mekanizma ön-kontrolü.
  `span_hinges` = açıklık İÇİNDE mafsal (açıklık no, sol uçtan a) → `expand()`
  açıklığı böler, araya `free` düğüm koyar, yükleri dağıtır (`_split_load`) ve
  `node_map` döndürür. **Çözüm/çizim hep genişletilmiş model üzerinden yapılır**;
  `solve()` tepkilerde `node`u kullanıcı numarasına geri çevirir, çizim
  `node_expanded`i kullanır. Bu ayrımı bozma.
  `springs` = elastik yay `{düğüm no: k [kN/m]}`; düğüm tipi `"spring"` OLMAK
  ZORUNDA. Yay varken `to_pycba` ham `R` vektörü kurar (PyCBA'da yay yalnız `R` ile
  verilir, `supports=` ile birlikte geçilemez). Yay `static_degree()`de tepki
  bileşenidir; dönme yayı yoktur.
  `settlements` = mesnet çökmesi `{düğüm no: düşey yer değiştirme [m]}` → PyCBA
  `D=` vektörüne. İşaret sehimle aynı (**aşağı negatif**). Yalnız mesnetli düğüme
  verilebilir; yay mesnede VERİLEMEZ (PyCBA o DOF'u sıfırlar, yay rijitliği devre
  dışı kalır).
- `core/solver.py` — `solve(model) -> dict` (diyagram dizileri, ekstremler,
  tepkiler, `analysis` nesnesi). Kararsız sistemde `SolverError`.
  `_map_reactions` kompakt tepki vektörünü mesnet tiplerine bakarak düğümlere eşler.
  **Yay mesnetler `R`de HİÇ GEÇMEZ**: kuvvet ayrı `Rs` vektöründe (`-k·u`); iki
  vektör ayrı ilerletilir. Sehim dizisi `res.D`den DEĞİL `_sehim_dizisi(vRes)`ten
  kurulur: PyCBA eleman uçlarındaki dolgu istasyonlarına sehim yazmaz (0 kalır).
  `build_beam(model)` şema çizimi için `pycba.Beam` verir.

Dikkat edilecekler:
- `Load.span` 1-tabanlıdır; `a` her zaman açıklığın **sol ucundan** ölçülür.
- Trapez yükte `a=0, c=0` "tüm açıklık" demektir.
- Sehim `D` metredir; arayüz mm'ye çevirir. Çökme de öyle: çekirdek m, arayüz mm.
- **Diyagram ızgarası `solver.ISTASYON_SAYISI` (=1000).** PyCBA ızgarası eşit
  aralıklıdır, süreksizliklere istasyon eklenmez; 100'de tepe değer %1 düşük
  okunuyordu. DÜŞÜRME (`test_tekil_yuk_tepe_degeri_izgaradan_kacmaz`). Artık hata
  README "Bilinen sınırlar"da yazılı.
- **PyCBA M/V dizilerinde eleman uçları eksene KAPANIR** (her elemanın ilk/son
  istasyonu tekrarlanır, 0 yazılır): bilinçli çizim geleneği, DÜZELTMEYE KALKMA.
  Aynı dolgu SEHİMDE yanlıştır, orası `_sehim_dizisi` ile onarılır.
- **Şema figürü `matplotlib.figure.Figure` ile kurulur, `plt.subplots()` ile
  DEĞİL** (`api/index._sema_svg`): pyplot global kayıt tutar, sunucu istekleri
  iş parçacığı havuzunda çalışır. Testlerde `plt.subplots()` sorun değil.
- **Şemada EI'nin görsel karşılığı YOKTUR** (bilerek): `ciz_sema` çiziciye EI'leri
  eşitlenmiş kopya verir; PyCBA aksi halde gövde çizip mesnet gliflerini yutar.
  Hesap gerçek EI ile. Muhafız: `tests/test_sema.py`.
- **Şema ölçeği içerikten bağımsızdır** (`ui_cizim._sabitle_olcek`): kutu genişliği
  `SEMA_KUTU_ORANI` ile sabit, figür yüksekliği veri en-boyundan türer.
  `ax.get_position(original=True)` şart; varsayılan aktif (daraltılmış) kutudur.
- Çökme İZOSTATİK sistemde kesit tesiri üretmez; ön yüz `static_degree() == 0`
  iken bilgi bandı gösterir.

## Dil (TR/EN)

İki katalog, ikisi de saf sözlük:
- `ui_dil.py` — arayüz metinleri (`cevir(dil, anahtar, **kw)`; `METINLER` API ile
  ön yüze gider, ön yüz Python biçim dizgesinin `{ad}`, `{ad:g}`, `{ad:.2f}`
  alt kümesini `web/lib/i18n.ts`de çözer).
- `core/mesajlar.py` — çekirdeğin kullanıcıya gösterilen hata mesajları.

Dil, çağıran katmandan **açık parametre** olarak geçer (`validate(dil)`,
`solve(model, dil)`, `ciz_sema(..., dil)`). Modül düzeyinde "geçerli dil" global'i
BİLEREK yok (iş parçacığı havuzunda kullanıcıdan kullanıcıya sızar). Varsayılan `tr`.

Kural: `web/` içine kullanıcıya görünen sabit dize YAZMA; `ui_dil.py`'ye iki dile
birden anahtar ekle (nokta ile gruplu: `mesnet.pin`, `yuk.udl`, `web.*`).
Birimler (kN, m, kNm²) çeviriye girmez. Yük/mesnet tipi eklerken `yuk.<kind>` +
`ipucu.<kind>` (veya `mesnet.<tip>`) satırlarını **iki dile de** ekle; anahtarlar
dize birleştirmesiyle kurulduğu için aramada görünmez, unutulursa yalnız
`tests/test_dil.py` yakalar.

## Dağıtım (Vercel, iki proje)

- **API:** repo kökünden `vercel deploy --prod` → `pycba-api`
  (https://pycba-api.vercel.app). Bağımlılıkları `pyproject.toml` belirler
  (`requirements.txt` `.vercelignore`da; ikisini aynı tut). `vercel.json` YAZMA:
  rewrite eklenince yol `/api/index`e dönüşüp FastAPI 404 verdi (ölçüldü).
  `.vercelignore` `web/`i, testleri ve belgeleri dışarıda tutar.
- **Ön yüz:** `web/` içinden `vercel deploy --prod` → `pycba-web`
  (https://pycba-web.vercel.app). `API_URL` ortam değişkeni (production) API
  adresidir; `next.config.mjs` rewrites'ı BUILD zamanında okur, değişince yeniden
  derle.
- AGPL 13. madde: çalışan uygulamada kaynak kod bağlantısı bulunmak zorunda
  (kenar çubuğu altbilgisi, `web/app/page.tsx`). Kaldırma.
- Soğuk başlangıç ölçülmedi; yavaşlık şikâyeti gelirse önce onu ölç.
