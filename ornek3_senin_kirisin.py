"""
PyCBA Ornek 3: KENDI KIRISINI TANIMLA
=====================================
Asagidaki TODO kismini sen dolduracaksin. Sonra calistirip
el hesabinla / ders notunla karsilastir.

HATIRLATMA - 4 liste ile kiris tanimlanir:
  L  : aciklik uzunluklari listesi, orn [5.0, 7.0, 5.0]
  EI : her aciklik icin egilme rijitligi, orn [60000, 60000, 60000]
  R  : mesnet kosullari. Her DUGUM icin [dusey, donme] cifti, sirayla.
        -1 = tutulu (rijit), 0 = serbest
        Ornekler:
          mafsalli/hareketli mesnet -> -1, 0
          ANKASTRE mesnet            -> -1, -1
          mesnet yok (serbest uc)    ->  0, 0
  LM : yuk matrisi, her satir = [aciklik_no, tip, deger, a, c]
        tip 1 = tum acikliga UDL (deger = kN/m)     -> a, c = 0
        tip 2 = tekil yuk (deger = kN, a = mesnetten uzaklik m)
        tip 3 = aciklik icinde kismi UDL (a..c arasi)
        tip 4 = moment yuku (deger = kN.m, a = konum)
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pycba as cba

# =====================================================================
# TODO (SENIN GOREVIN):
#   3 aciklikli, soldaki mesnedi ANKASTRE olan bir surekli kiris kur.
#   - Aciklik uzunluklari sana kalmis (orn 5, 6, 5 m)
#   - Orta aciklikta bir TEKIL yuk (tip 2) ekle, kenar acikliklarda UDL
#   Neden onemli: ankastre mesnet, mafsala gore momenti nasil degistirir?
#   Calistirinca ankastre ucta sifir-olmayan moment gormeli, mafsalda
#   sifir moment gormelisin. Tahminini kodu calistirmadan once yaz!
# =====================================================================

L  = [ ]   # <-- doldur, orn [5.0, 6.0, 5.0]
EI = [ ]   # <-- doldur, orn [60000, 60000, 60000]
R  = [ ]   # <-- doldur. Sol dugum ankastre (-1,-1), digerleri mafsal (-1,0)
LM = [ ]   # <-- doldur. orn [[1,1,15,0,0],[2,2,40,3,0],[3,1,15,0,0]]

# ---------------------------------------------------------------------
# Buradan asagisi hazir - dokunmana gerek yok
# ---------------------------------------------------------------------
ba = cba.BeamAnalysis(L, EI, R, LM)
ba.analyze()

print("Mesnet tepkileri (kN):", np.round(ba.beam_results.R, 2))
res = ba.beam_results.results
print(f"Max (+) moment: {np.max(res.M):7.2f} kN.m")
print(f"Min (-) moment: {np.min(res.M):7.2f} kN.m")

ba.plot_results()
plt.savefig("senin_kirisin.png", dpi=120, bbox_inches="tight")
print("Diyagram -> senin_kirisin.png")
