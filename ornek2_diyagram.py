"""
PyCBA Örnek 2: Diyagram çizimi (moment / kesme / sehim)
Aynı 2 açıklıklı kirişin sonuç diyagramlarını PNG olarak kaydeder.

Bu betik ham PyCBA'yı kullanır (core/ katmanından geçmez); amacı kütüphanenin
kendi çizim çıktısını göstermektir. Çekirdeği doğrulayan örnek
`ornek1_surekli_kiris.py`'dir.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")          # ekran olmadan dosyaya çizim için
import matplotlib.pyplot as plt
import pycba as cba

# Çıktı depo köküne DEĞİL, gitignore'lanmış cikti/ dizinine yazılır: izlenen bir
# örneği çalıştırmak `git status`u kirletmemeli.
CIKTI = Path(__file__).parent / "cikti"

L  = [6.0, 6.0]
EI = [60000.0, 60000.0]
R  = [-1, 0, -1, 0, -1, 0]
LM = [[1, 1, 20, 0, 0], [2, 1, 20, 0, 0]]

ba = cba.BeamAnalysis(L, EI, R, LM)
ba.analyze()

# PyCBA'nın yerleşik çizim fonksiyonu: moment, kesme, sehim alt grafikleri
ba.plot_results()
CIKTI.mkdir(exist_ok=True)
hedef = CIKTI / "sonuc_diyagram.png"
plt.savefig(hedef, dpi=120, bbox_inches="tight")
print(f"Diyagram kaydedildi -> {hedef}")
