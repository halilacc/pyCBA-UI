"""
PyCBA Ornek 2: Diyagram cizimi (moment / kesme / sehim)
Ayni 2 aciklikli kirisin sonuc diyagramlarini PNG olarak kaydeder.
"""
import matplotlib
matplotlib.use("Agg")          # ekran olmadan dosyaya cizim icin
import matplotlib.pyplot as plt
import pycba as cba

L  = [6.0, 6.0]
EI = [60000.0, 60000.0]
R  = [-1, 0, -1, 0, -1, 0]
LM = [[1, 1, 20, 0, 0], [2, 1, 20, 0, 0]]

ba = cba.BeamAnalysis(L, EI, R, LM)
ba.analyze()

# PyCBA'nin yerlesik cizim fonksiyonu: moment, kesme, sehim alt grafikleri
ba.plot_results()
plt.savefig("sonuc_diyagram.png", dpi=120, bbox_inches="tight")
print("Diyagram kaydedildi -> sonuc_diyagram.png")
