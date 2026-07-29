"""
Kiriş modeli veri sınıfları.

Bu modül arayüzden (Streamlit vb.) tamamen bağımsızdır: yalnızca modeli tanımlar,
doğrular ve PyCBA'nın `BeamAnalysis` kurucusunun beklediği argümanlara çevirir.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .mesajlar import mesaj


# UI dropdown'ı ile PyCBA `supports=` adları birebir aynı (pycba.utils._SUPPORT_DOF).
# "spring" bunun İSTİSNASIDIR: PyCBA'nın `supports=` kısayolunda yay yoktur, yay
# ancak ham `R` vektörüyle verilir (bkz. to_pycba). Ad yine de "spring" seçildi;
# PyCBA'nın çizici glif sabiti de böyle (`render.py`: SPRING = "spring"), yani
# şema bedavaya doğru çizilir.
SUPPORT_TYPES = ["pin", "roller", "fixed", "free", "spring"]

# Mesnet tipi -> PyCBA ham DOF çifti (düşey, dönme): -1 tutulu, 0 serbest.
# Yay bu tabloda yoktur; katsayısı düğüm başına `BeamModel.springs`ten gelir.
_SUPPORT_DOF = {
    "pin": (-1, 0), "roller": (-1, 0), "fixed": (-1, -1), "free": (0, 0),
}

# Yük tipi -> (PyCBA LM kodu, insan-okur ad, parametre adları)
# LM satır formatları (pycba.analysis.BeamAnalysis docstring):
#   1 UDL           [span, 1, w]
#   2 Tekil yük     [span, 2, P, a]
#   3 Kısmi UDL     [span, 3, w, a, c]
#   4 Moment        [span, 4, M, a]
#   5 Trapez        [span, 5, w1, w2] veya [span, 5, w1, w2, a, c]
LOAD_TYPES = {
    "udl": (1, "Yayılı yük (UDL)", ["w"]),
    "point": (2, "Tekil yük", ["P", "a"]),
    "partial_udl": (3, "Kısmi yayılı yük", ["w", "a", "c"]),
    "moment": (4, "Moment", ["M", "a"]),
    "trapezoid": (5, "Trapez yük", ["w1", "w2", "a", "c"]),
    # Eksenel yükler PyCBA'ya gitmez (LM kodu None); core/axial.py çözer.
    # İşaret: pozitif değer +x (sağa) yönündedir.
    "axial_point": (None, "Eksenel tekil yük", ["N", "a"]),
    "axial_udl": (None, "Eksenel yayılı yük", ["n"]),
}

# PyCBA'ya çevrilmeyen, core/axial.py'nin çözdüğü yük tipleri.
AXIAL_KINDS = {k for k, v in LOAD_TYPES.items() if v[0] is None}


def check_load_position(kind: str, values: List[float], L: float,
                        dil: str = None) -> Optional[str]:
    """Konum parametrelerinin açıklık içinde kaldığını denetle.

    `a` her zaman açıklığın SOL ucundan ölçülür; `c` yayılı yükün uzunluğudur.
    Hata varsa açıklayıcı mesaj, yoksa None döndürür. `dil` verilmezse mesajlar
    Türkçedir (bkz. core/mesajlar.py).
    """
    if kind in ("point", "moment", "axial_point"):
        a = values[1]
        if not (0 <= a <= L):
            return mesaj("konum_aciklik_disinda", dil, a=a, L=L)
    elif kind in ("partial_udl", "trapezoid"):
        if kind == "partial_udl":
            _, a, c = values
        else:
            _, _, a, c = values
            if a == 0 and c == 0:
                return None  # trapez kısayolu: tüm açıklığa yayılır
        if a < 0:
            return mesaj("a_negatif", dil)
        if c <= 0:
            # Trapezde "tüm açıklık" kısayolu olduğu için ipucu farklı.
            return mesaj("c_pozitif" if kind == "partial_udl" else "c_pozitif_trapez", dil)
        if a + c > L + 1e-9:
            return mesaj("yuk_aciligi_asiyor", dil, ac=a + c, L=L)
    return None


@dataclass
class Load:
    """Tek bir yük tanımı.

    span : 1-tabanlı açıklık numarası
    kind : LOAD_TYPES anahtarlarından biri
    values : LOAD_TYPES[kind] parametre sırasıyla sayısal değerler
             (trapez için a=c=0 verilirse tüm açıklığa yayılır)
    """

    span: int
    kind: str
    values: List[float] = field(default_factory=list)

    def check_params(self, dil: str = None) -> None:
        """Parametre sayısını denetle; uyuşmazlıkta ValueError."""
        _, _, params = LOAD_TYPES[self.kind]
        if len(self.values) != len(params):
            raise ValueError(mesaj(
                "yuk_parametre_sayisi", dil, kind=self.kind,
                beklenen=len(params), adlar=", ".join(params),
                verilen=len(self.values),
            ))

    def to_lm_row(self) -> list:
        if self.kind in AXIAL_KINDS:
            raise ValueError(f"'{self.kind}' eksenel yüktür; PyCBA LM satırına çevrilemez.")
        code, _, params = LOAD_TYPES[self.kind]
        vals = list(self.values)
        self.check_params()
        if self.kind == "trapezoid" and vals[2] == 0 and vals[3] == 0:
            vals = vals[:2]  # tam-açıklık trapez: [span, 5, w1, w2]
        return [self.span, code] + vals


def _split_load(ld: "Load", parcalar: List[tuple]) -> List["Load"]:
    """Bir yükü, açıklığın bölündüğü alt açıklıklara dağıt.

    parcalar : [(yeni_açıklık_no, s, e), ...] — alt açıklığın ORİJİNAL açıklık
               koordinatındaki [s, e] aralığı, soldan sağa sıralı.
    Dönüş: alt açıklıklara ait yeni Load nesneleri (etki eden olmayan alt
    açıklık için satır üretilmez).
    """
    if len(parcalar) == 1:  # bölünme yok
        return [Load(parcalar[0][0], ld.kind, list(ld.values))]

    kind = ld.kind
    if kind in ("udl", "axial_udl"):
        # Tüm açıklığa yayılı: her alt açıklıkta aynı şiddetle tüm açıklık.
        return [Load(ns, kind, list(ld.values)) for ns, _, _ in parcalar]

    if kind in ("point", "moment", "axial_point"):
        P, a = ld.values
        for ns, s, e in parcalar:
            # Kesim noktasına tam denk gelen yük SAĞDAKİ alt açıklığın sol ucuna
            # verilir (a=0); son parçada sağ uç da dahildir.
            if s <= a < e or (ns == parcalar[-1][0] and a <= e + 1e-9):
                return [Load(ns, kind, [P, min(max(a - s, 0.0), e - s)])]
        ns, s, e = parcalar[-1]
        return [Load(ns, kind, [P, e - s])]

    if kind == "partial_udl":
        w, a, c = ld.values
        out = []
        for ns, s, e in parcalar:
            ov_s, ov_e = max(a, s), min(a + c, e)
            if ov_e - ov_s > 1e-9:
                out.append(Load(ns, kind, [w, ov_s - s, ov_e - ov_s]))
        return out

    if kind == "trapezoid":
        w1, w2, a, c = ld.values
        if a == 0 and c == 0:  # tam açıklık kısayolu — gerçek aralığa aç
            a, c = 0.0, parcalar[-1][2]
        out = []
        for ns, s, e in parcalar:
            ov_s, ov_e = max(a, s), min(a + c, e)
            if ov_e - ov_s <= 1e-9:
                continue
            # Şiddet a..a+c arasında lineer; kesim noktalarındaki değer
            # interpolasyonla bulunur, böylece toplam yük korunur.
            ws = w1 + (w2 - w1) * (ov_s - a) / c
            we = w1 + (w2 - w1) * (ov_e - a) / c
            if abs(ov_s - s) < 1e-9 and abs(ov_e - e) < 1e-9:
                out.append(Load(ns, kind, [ws, we, 0.0, 0.0]))  # alt açıklığın tamamı
            else:
                out.append(Load(ns, kind, [ws, we, ov_s - s, ov_e - ov_s]))
        return out

    raise ValueError(f"'{kind}' yükü açıklık içi mafsalla bölünemiyor.")


@dataclass
class BeamModel:
    """Sürekli kiriş modeli.

    spans    : açıklık uzunlukları [m], N eleman
    EI       : her açıklığın eğilme rijitliği [kNm²], N eleman
    supports : her düğümün mesnet tipi (SUPPORT_TYPES), N+1 eleman
    loads    : yük listesi
    hinges   : DÜĞÜMDE (mesnet hizasında) mafsallı düğüm no'ları (1-tabanlı,
               yalnız ara düğümler) — Gerber; boş liste = tam sürekli kiriş
    span_hinges : AÇIKLIK İÇİNDE mafsallar: (açıklık no, sol uçtan a [m]) çiftleri.
               `expand()` bunları açıklığı bölerek mesnetsiz (free) düğüme çevirir;
               kullanıcı açıklıklarını ve yük numaralandırmasını elle bölmek zorunda
               kalmaz.
    springs : elastik yay mesnetlerin DÜŞEY yay katsayısı
               {düğüm no (1-tabanlı): k [kN/m]}. Yalnız `supports[i] == "spring"`
               olan düğümler için verilir (ikisi birlikte zorunludur). Düğüm
               düşeyde tutulu değildir, k·δ kadar tepki verir; k büyüdükçe
               davranış kayıcı mesnede yaklaşır. Dönme yayı YOKTUR (PyCBA
               destekler ama arayüz düşey yayla sınırlıdır).
    settlements : mesnet çökmeleri {düğüm no (1-tabanlı): düşey yer değiştirme [m]}.
               İŞARET sehim `D` ile aynıdır: aşağı NEGATİF. (Arayüz "çökme"yi
               pozitif aldığı için mm'yi işaret çevirerek buraya yazar.) Yalnız
               mesnetli düğüme verilebilir; PyCBA'ya öngörülmüş yer değiştirme
               vektörü (`D=`) olarak gider. İzostatik sistemde kesit tesiri
               doğurmaz — kiriş yalnız rijit olarak yer değiştirir.
    """

    spans: List[float]
    EI: List[float]
    supports: List[str]
    loads: List[Load] = field(default_factory=list)
    hinges: List[int] = field(default_factory=list)
    span_hinges: List[tuple] = field(default_factory=list)
    springs: Dict[int, float] = field(default_factory=dict)
    settlements: Dict[int, float] = field(default_factory=dict)

    @property
    def n_spans(self) -> int:
        return len(self.spans)

    @property
    def n_nodes(self) -> int:
        return len(self.spans) + 1

    def validate(self, dil: str = None) -> List[str]:
        """Hata mesajları listesi döndürür; boş liste = model geçerli.

        `dil` verilmezse mesajlar Türkçedir (bkz. core/mesajlar.py).
        """
        errors = []

        def hata(anahtar, **kw):
            errors.append(mesaj(anahtar, dil, **kw))

        if not self.spans:
            hata("aciklik_yok")
        if any(L <= 0 for L in self.spans):
            hata("aciklik_pozitif")
        if len(self.EI) != self.n_spans:
            hata("ei_sayisi", n_ei=len(self.EI), n_span=self.n_spans)
        if any(ei <= 0 for ei in self.EI):
            hata("ei_pozitif")
        if len(self.supports) != self.n_nodes:
            hata("mesnet_sayisi", n_sup=len(self.supports), n_node=self.n_nodes)
        for s in self.supports:
            if s not in SUPPORT_TYPES:
                hata("mesnet_tipi", tip=s)
        # Mafsal yalnız ARA düğüme konur: uç düğümde tek eleman vardır, orada
        # "mafsal" zaten mesnet tipinin (pin/roller) işidir.
        gorulen = set()
        for h in self.hinges:
            if not (2 <= h <= self.n_nodes - 1):
                hata("mafsal_dugum_gecersiz", h=h, son=self.n_nodes - 1)
            elif h in gorulen:
                hata("mafsal_tekrar", h=h)
            gorulen.add(h)
        # Açıklık içi mafsal: konum açıklığın İÇİNDE olmalı (uçta olsaydı bu
        # zaten düğüm mafsalıdır — `hinges` ile verilir).
        gorulen_ic = set()
        for sp, a in self.span_hinges:
            if not (1 <= sp <= self.n_spans):
                hata("ic_mafsal_aciklik_gecersiz", sp=sp, n_span=self.n_spans)
                continue
            L = self.spans[sp - 1]
            if not (1e-9 < a < L - 1e-9):
                hata("ic_mafsal_konum", sp=sp, a=a, L=L)
            elif (sp, round(a, 9)) in gorulen_ic:
                hata("ic_mafsal_tekrar", sp=sp, a=a)
            gorulen_ic.add((sp, round(a, 9)))
        # Yay mesnet: tip ile katsayı BİRLİKTE verilmelidir. Tek başına "spring"
        # tipi katsayısız bir yay (sonsuz esnek = serbest) demek olurdu; tek
        # başına katsayı ise sessizce yok sayılırdı.
        if len(self.supports) == self.n_nodes:
            for i, s in enumerate(self.supports, start=1):
                if s == "spring" and i not in self.springs:
                    hata("yay_katsayisi_yok", n=i)
        for n, k in self.springs.items():
            if not (1 <= n <= self.n_nodes):
                hata("yay_dugum_gecersiz", n=n, son=self.n_nodes)
                continue
            if len(self.supports) == self.n_nodes and self.supports[n - 1] != "spring":
                hata("yay_mesnet_tipi", n=n)
            try:
                gecerli = math.isfinite(float(k)) and float(k) > 0
            except (TypeError, ValueError):
                gecerli = False
            if not gecerli:
                hata("yay_katsayisi_pozitif", n=n)
        # Mesnet çökmesi: mesnetsiz (free) düğüme verilemez. Fiziksel gerekçe,
        # oradaki düğümün zaten serbestçe hareket ediyor olması; pratik gerekçe,
        # solver._map_reactions'ın tepki vektörünü mesnet tiplerinden okuması —
        # serbest düğüme dayatılan yer değiştirmenin ürettiği kuvvet PyCBA'nın
        # tepki listesine girmez ve sessizce kaybolurdu.
        for n, d in self.settlements.items():
            if not (1 <= n <= self.n_nodes):
                hata("cokme_dugum_gecersiz", n=n, son=self.n_nodes)
                continue
            if len(self.supports) == self.n_nodes and self.supports[n - 1] == "free":
                hata("cokme_mesnetsiz", n=n)
            # Yay mesnede çökme verilemez: PyCBA'da öngörülmüş yer değiştirme o
            # DOF'un satır/sütununu sıfırlar (analysis._apply_bc), yani yay
            # rijitliği devre dışı kalır ve düğüm "çöken ANKASTRE mesnet" gibi
            # davranır. Kullanıcının kastettiği (yayın ZEMİN ucunun oturması,
            # kuvvetin k·(u−Δ) olması) bu değildir; sessizce yanlış model
            # kurmaktansa reddedilir.
            elif n in self.springs:
                hata("cokme_yay_mesnet", n=n)
            try:
                sonlu = math.isfinite(float(d))
            except (TypeError, ValueError):
                sonlu = False
            if not sonlu:
                hata("cokme_sayisal", n=n)
        for i, ld in enumerate(self.loads, start=1):
            if ld.kind not in LOAD_TYPES:
                hata("yuk_tipi_bilinmeyen", i=i, kind=ld.kind)
                continue
            if not (1 <= ld.span <= self.n_spans):
                hata("yuk_aciklik_gecersiz", i=i, sp=ld.span, n_span=self.n_spans)
            try:
                ld.check_params(dil)
            except ValueError as e:
                hata("yuk_oneki", i=i, mesaj=str(e))
                continue
            if 1 <= ld.span <= self.n_spans:
                pos_err = check_load_position(
                    ld.kind, ld.values, self.spans[ld.span - 1], dil
                )
                if pos_err:
                    hata("yuk_oneki", i=i, mesaj=pos_err)
        return errors

    def expand(self):
        """Açıklık içi mafsalları düğüm mafsalına çevirerek genişletilmiş model üret.

        PyCBA'da (ve bu modelde) mafsal yalnız eleman ucuna konabilir. Kullanıcı
        mafsalı açıklığın ortasına koymak istediğinde açıklık o noktadan ikiye
        bölünür ve araya MESNETSİZ (`free`) bir düğüm girer — statikteki standart
        Gerber modellemesinin aynısı. Bölme burada otomatik yapılır ki kullanıcı
        açıklık uzunluklarını ve yük numaralandırmasını elle bölmek zorunda kalmasın.

        Dönüş: (genisletilmis_model, node_map)
            node_map[i] = genişletilmiş modelin (i+1). düğümünün ORİJİNAL düğüm
            no'su; bölme sonucu doğan yeni düğümler için None. Sunum katmanı
            tepkileri kullanıcının numaralandırmasına bununla geri çevirir.

        Açıklık içi mafsal yoksa modelin kendisi ve birebir eşleme döner (kopya
        maliyeti yok, mevcut davranış değişmez).
        """
        if not self.span_hinges:
            return self, list(range(1, self.n_nodes + 1))

        yeni_spans, yeni_EI = [], []
        yeni_supports = [self.supports[0]]
        node_map = [1]
        yeni_hinges, yeni_loads = [], []
        parca_haritasi = {}  # orijinal açıklık no -> [(yeni no, s, e), ...]

        for i in range(1, self.n_spans + 1):
            L = float(self.spans[i - 1])
            kesimler = sorted(a for sp, a in self.span_hinges if sp == i)
            sinirlar = [0.0] + kesimler + [L]
            parcalar = []
            for j in range(len(sinirlar) - 1):
                yeni_spans.append(sinirlar[j + 1] - sinirlar[j])
                yeni_EI.append(self.EI[i - 1])
                parcalar.append((len(yeni_spans), sinirlar[j], sinirlar[j + 1]))
                if j < len(sinirlar) - 2:
                    # Kesim noktasındaki yeni düğüm: mesnetsiz + mafsallı.
                    yeni_supports.append("free")
                    node_map.append(None)
                    yeni_hinges.append(len(yeni_supports))
                else:
                    yeni_supports.append(self.supports[i])
                    node_map.append(i + 1)
            parca_haritasi[i] = parcalar

        # Kullanıcının düğüm mafsalları yeni numaralandırmaya taşınır.
        yeni_hinges += [node_map.index(h) + 1 for h in self.hinges]
        for ld in self.loads:
            yeni_loads += _split_load(ld, parca_haritasi[ld.span])

        genis = BeamModel(
            spans=yeni_spans, EI=yeni_EI, supports=yeni_supports,
            loads=yeni_loads, hinges=sorted(yeni_hinges),
            # Yay katsayıları da yeni numaralandırmaya taşınır (çökmelerle aynı
            # yolla): bölme, yayın verildiği düğümün no'sunu kaydırır.
            springs={node_map.index(n) + 1: k for n, k in self.springs.items()},
            # Çökmeler de yeni numaralandırmaya taşınır (mafsallarla aynı yolla):
            # bölme, çökmenin verildiği mesnedin düğüm no'sunu kaydırır.
            settlements={node_map.index(n) + 1: d
                         for n, d in self.settlements.items()},
        )
        return genis, node_map

    def eletypes(self) -> List[int]:
        """Mafsal listesini PyCBA `eletype` koduna çevir (açıklık başına 1 kod).

        PyCBA'da mafsal düğüme değil ELEMANA konur: bir iç mafsalda birleşen iki
        elemandan **yalnız biri** moment salıverir (pycba.MemberType docstring).
        Kural: mafsal her zaman SAĞDAKİ elemanın sol ucuna verilir — böylece her
        açıklık en fazla bir salıverme alır ve kod tekilleşir:
            FF (1) = iki ucu sürekli, PF (3) = sol ucu mafsallı.
        Açıklık i'nin (1-tabanlı) sol düğümü i olduğundan, düğüm i mafsallıysa
        açıklık i PF olur. Düğüm 1'e mafsal konamadığı için ilk açıklık hep FF'dir.
        """
        h = set(self.hinges)
        return [3 if i in h else 1 for i in range(1, self.n_spans + 1)]

    def static_degree(self) -> int:
        """Eğilme sisteminin statik belirsizlik derecesini döndür.

        Kiriş, mafsallarda h+1 rijit parçaya ayrılır. Düzlemde düşey yükleme
        için parça başına 2 denge denklemi (ΣFy, ΣM) vardır; bilinmeyenler
        mesnet tepki bileşenleri (pin/roller 1, ankastre 2, serbest 0) ile her
        mafsalın aktardığı kesme kuvvetidir (h adet). Buradan:

            derece = r + h - 2(h + 1) = r - h - 2

        > 0 hiperstatik, = 0 izostatik, < 0 mekanizma (kararsız).
        PyCBA yatay DOF tutmadığı için bu sayım yalnız eğilme sistemini kapsar;
        eksenel sistem `core/axial.py`'de ayrı denetlenir.

        Açıklık içi mafsallar da sayılır: `expand()` onları mesnetsiz düğüme
        çevirdiği için tepki sayısını değiştirmez, yalnız h'yi artırır — yani
        genişletilmiş model için de aynı sonucu verir.

        Elastik yay mesnet TEPKİ BİLEŞENİ sayılır (r += 1): düşey hareketi
        engellemez ama kuvvetle karşı koyduğu için rijit yer değiştirmeyi
        önler, yani mekanizma sayımında kayıcı mesnetle aynı rolü oynar.
        (Kuvveti denge denklemlerinden değil rijitlikten çıkar; bu yüzden yaylı
        sistem "hiperstatik" görünür — doğrudur, çözüm k'ya bağlıdır.)
        """
        r = sum({"pin": 1, "roller": 1, "fixed": 2, "free": 0, "spring": 1}.get(s, 0)
                for s in self.supports)
        return r - len(self.hinges) - len(self.span_hinges) - 2

    def to_pycba(self, dil: str = None) -> dict:
        """`BeamAnalysis(**model.to_pycba())` ile doğrudan kullanılabilir sözlük.

        `dil` yalnız doğrulama hatasının dilini belirler (bkz. core/mesajlar.py).
        """
        errors = self.validate(dil)
        if errors:
            raise ValueError(" / ".join(errors))
        # Eksenel yükler PyCBA'ya gitmez (core/axial.py çözer); LM boş kalırsa
        # None geçilir — PyCBA boş yük matrisiyle sıfır sonuç üretir.
        lm = [ld.to_lm_row() for ld in self.loads if ld.kind not in AXIAL_KINDS]
        # Öngörülmüş yer değiştirme vektörü: düğüm başına (düşey, dönme) iki
        # girdi, bilinmeyen DOF'lar için None. Çökme yalnız DÜŞEY DOF'a yazılır;
        # dönme serbest bırakılır (mesnet oturur, dönmesi engellenmez). Çökme
        # yoksa None geçilir — PyCBA'nın varsayılan davranışı birebir korunur.
        D = None
        if self.settlements:
            D = [None] * (2 * self.n_nodes)
            for n, d in self.settlements.items():
                D[2 * (n - 1)] = float(d)
        arg = {
            "L": list(self.spans),
            "EI": list(self.EI),
            "LM": lm or None,
            "eletype": self.eletypes(),
            "D": D,
        }
        # Mesnetler: normalde PyCBA'nın dostane `supports=` adları geçilir.
        # Yay varsa bu YOL KAPALIDIR — `_SUPPORT_DOF` sözlüğünde yay yoktur ve
        # `supports` ile `R` birlikte verilemez (analysis.py:152). O durumda ham
        # `R` vektörü kurulur: düğüm başına (düşey, dönme); -1 tutulu, 0 serbest,
        # +k yay rijitliği (analysis.py:95-103). Yay yokken eski yol korunur ki
        # mevcut davranış bit düzeyinde aynı kalsın.
        if self.springs:
            R = []
            for i, s in enumerate(self.supports, start=1):
                if s == "spring":
                    R += [float(self.springs[i]), 0]
                else:
                    R += list(_SUPPORT_DOF[s])
            arg["R"] = R
        else:
            arg["supports"] = list(self.supports)
        return arg
