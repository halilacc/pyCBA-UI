# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proje

PyCBA (sürekli kiriş analizi kütüphanesi) üzerine kurulmuş Streamlit web arayüzü.
PyCBA fork edilmez, `.venv` içinden bağımlılık olarak `import` edilir. Git deposu değildir.
Tüm kod/yorum dili Türkçe; buna uy. Detaylı tasarım kararları: `pyCBA-UI-Planı.md`.

## Komutlar

```powershell
# Uygulamayı çalıştır (sargısız — streamlit.exe kullanma, aşağıya bak)
.venv\Scripts\python.exe -m streamlit run app.py

# Bağımlılıklar
.venv\Scripts\pip.exe install -r requirements.txt

# Çekirdeği UI olmadan doğrula (test altyapısı yok; doğrulama böyle yapılır)
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

## Mimari

Temel ilke: **hesap mantığı arayüzden tamamen ayrı.** `core/` Streamlit'e hiç bağımlı
değildir; arayüz ileride Gradio/Flask ile değiştirilebilmelidir. UI mantığını asla
`core/`e, hesap mantığını asla `app.py`'ye koyma.

- `core/model.py` — `BeamModel` ve `Load` dataclass'ları, doğrulama (`validate()` hata
  mesajı listesi döndürür), PyCBA argümanlarına çeviri (`to_pycba()`). `LOAD_TYPES`
  sözlüğü yük tipi → PyCBA LM kodu + parametre adları eşlemesinin tek kaynağıdır;
  yeni yük tipi eklemek çoğunlukla buraya (ve `app.py`'deki `PARAM_LABELS`/`KIND_HINTS`
  etiketlerine) satır eklemektir.
- `core/solver.py` — `solve(model) -> dict` (diyagram dizileri, ekstremler, tepkiler,
  `analysis` nesnesi). Kararsız sistemde kullanıcıya gösterilebilir `SolverError`
  fırlatır. `_map_reactions` PyCBA'nın kompakt tepki vektörünü (yalnızca tutulu DOF'lar,
  düğüm başına düşey+dönme sırasıyla) mesnet tiplerine bakarak düğümlere eşler.
  `build_beam(model)` analiz çalıştırmadan şema çizimi için `pycba.Beam` verir.
- `app.py` — yalnızca sunum: sidebar'da girdi, `st.session_state.loads` içinde yük
  listesi, sonuçlar Plotly ile (`plot_results(backend="plotly")`).

PyCBA API referansı (LM satır formatları, `supports=` adları, sonuç erişimi) plan
dosyasının "PyCBA API" bölümünde satır numaralarıyla belgelidir; kaynak
`.venv/Lib/site-packages/pycba/`.

Dikkat edilecekler:
- `Load.span` 1-tabanlıdır; `a` konumu her zaman açıklığın **sol ucundan** ölçülür.
- Trapez yükte `a=0, c=0` "tüm açıklık" demektir; `to_lm_row` bu durumda a/c'yi düşürür.
- `app.py`'deki konum girdilerinin `key`'i açıklık no ve L'ye bağlıdır — açıklık
  değişince bayat değer taşınmasın diye; bu deseni bozma.
- Sehim `D` metre cinsindendir; UI mm'ye çevirerek gösterir.

## 2. Aşama (henüz yok)

Kiriş fotoğrafından model çıkarma (LLM ile) planlanıyor; formu ön-dolduracak, `core/`
değişmeyecek. Bkz. plan dosyası.
