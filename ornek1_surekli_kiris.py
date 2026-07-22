"""
PyCBA Ornek 1: Iki aciklikli surekli kiris
-------------------------------------------
Yapi Statigi dersinin klasik problemi.

   q = 20 kN/m (tum kiris boyunca duzgun yayili yuk)
   |||||||||||||||||||||||||||||||
   ^----------- 6 m -----------^----------- 6 m -----------^
  A (mafsal)              B (mafsal)              C (mafsal)

Beklenen: B mesnedinde negatif (cekme ust lifte) moment olusur,
acikliklarda pozitif moment olusur. El ile cozumde M_B = -q*L^2/8.
"""
import pycba as cba

# --- 1) Kiris geometrisi ve malzeme ---
L = [6.0, 6.0]            # iki acikligin uzunlugu [m]
EI = 30 * 1e7 * 1e-6 * 2  # ornek bir EI degeri [kN.m^2] (E*I)
EI = [EI, EI]             # her aciklik icin

# --- 2) Mesnet kosullari: her dugumde [dusey, donme]; -1 = tutulu, 0 = serbest ---
# A, B, C dugumlerinin hepsi mafsalli mesnet (dusey tutulu, donme serbest)
R = [-1, 0, -1, 0, -1, 0]

# --- 3) Yuk matrisi: [aciklik_no, yuk_tipi, deger, a, c] ---
# yuk_tipi 1 = tum acikliga duzgun yayili yuk (UDL)
LM = [[1, 1, 20, 0, 0],
      [2, 1, 20, 0, 0]]

# --- 4) Analiz ---
beam_analysis = cba.BeamAnalysis(L, EI, R, LM)
beam_analysis.analyze()

# --- 5) Sonuclar ---
print("=== MESNET TEPKILERI ===")
print(beam_analysis.beam_results.R)   # tepki kuvvetleri

import numpy as np
res = beam_analysis.beam_results.results
M = res.M       # moment dizisi
V = res.V       # kesme kuvveti dizisi
x = res.x       # konum dizisi

print("\n=== KESIT TESIRLERI (ozet) ===")
print(f"Maksimum (+) moment : {np.max(M):8.2f} kN.m")
print(f"Minimum  (-) moment : {np.min(M):8.2f} kN.m  (B mesnedi civari)")
print(f"Maksimum kesme      : {np.max(np.abs(V)):8.2f} kN")
print(f"\nEl ile beklenen M_B = -q*L^2/8 = {-20*6**2/8:.2f} kN.m")


# --- 6) ÇEKIRDEK (core/) DOGRULAMASI ---
# Yukaridaki blok ham PyCBA'yi test eder; asagidaki blok ayni referans problemi
# core.model + core.solve uzerinden kurup cozerek CEKIRDEK katmanini dogrular.
# Boylece core/solver.py (_map_reactions) veya core/model.py (to_lm_row) icindeki
# bir regresyon burada yakalanir. Beklenen: M_B = -90 kNm, tepkiler 45/150/45 kN.
from core import BeamModel, Load, solve

model = BeamModel(
    spans=[6.0, 6.0],
    EI=[EI[0], EI[1]],
    supports=["pin", "pin", "pin"],
    loads=[Load(1, "udl", [20]), Load(2, "udl", [20])],
)
r = solve(model)

M_B = r["Mmin"]                     # B mesnedindeki negatif moment (ekstrem negatif)
# Cekirdek tepkileri dugum sirasiyla [A, B, C]; ustteki ham 'V' dizisiyle
# karismasin diye ayri isim.
V_core = [rx["V"] for rx in r["reactions"]]

print("\n=== CEKIRDEK (core.solve) DOGRULAMASI ===")
print(f"core M_B      : {M_B:8.2f} kN.m  (beklenen -90.00)")
print(f"core tepkiler : {V_core[0]:.2f} / {V_core[1]:.2f} / {V_core[2]:.2f} kN  (beklenen 45 / 150 / 45)")

assert abs(M_B - (-90.0)) < 1e-6, f"M_B beklenen -90, cikti {M_B}"
assert abs(V_core[0] - 45.0) < 1e-6, f"A tepkisi beklenen 45, cikti {V_core[0]}"
assert abs(V_core[1] - 150.0) < 1e-6, f"B tepkisi beklenen 150, cikti {V_core[1]}"
assert abs(V_core[2] - 45.0) < 1e-6, f"C tepkisi beklenen 45, cikti {V_core[2]}"
print("CEKIRDEK DOGRULAMASI GECTI (core, referans degerleri koruyor).")
