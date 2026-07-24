"""
Kiriş modeli veri sınıfları.

Bu modül arayüzden (Streamlit vb.) tamamen bağımsızdır: yalnızca modeli tanımlar,
doğrular ve PyCBA'nın `BeamAnalysis` kurucusunun beklediği argümanlara çevirir.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# UI dropdown'ı ile PyCBA `supports=` adları birebir aynı (pycba.utils._SUPPORT_DOF).
SUPPORT_TYPES = ["pin", "roller", "fixed", "free"]

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


def check_load_position(kind: str, values: List[float], L: float) -> Optional[str]:
    """Konum parametrelerinin açıklık içinde kaldığını denetle.

    `a` her zaman açıklığın SOL ucundan ölçülür; `c` yayılı yükün uzunluğudur.
    Hata varsa açıklayıcı mesaj, yoksa None döndürür.
    """
    if kind in ("point", "moment", "axial_point"):
        a = values[1]
        if not (0 <= a <= L):
            return f"Konum a={a:g} m açıklık dışında (0 ile {L:g} m arasında olmalı)."
    elif kind == "partial_udl":
        _, a, c = values
        if a < 0:
            return "Başlangıç konumu a negatif olamaz."
        if c <= 0:
            return "Yayılı uzunluk c pozitif olmalı."
        if a + c > L + 1e-9:
            return (
                f"Yük açıklığı aşıyor: a+c = {a + c:g} m > L = {L:g} m. "
                "Başlangıç konumunu veya uzunluğu küçültün."
            )
    elif kind == "trapezoid":
        _, _, a, c = values
        if a == 0 and c == 0:
            return None  # tüm açıklığa yayılır
        if a < 0:
            return "Başlangıç konumu a negatif olamaz."
        if c <= 0:
            return "Yayılı uzunluk c pozitif olmalı (tüm açıklık için a=0, c=0 girin)."
        if a + c > L + 1e-9:
            return (
                f"Yük açıklığı aşıyor: a+c = {a + c:g} m > L = {L:g} m. "
                "Başlangıç konumunu veya uzunluğu küçültün."
            )
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

    def check_params(self) -> None:
        """Parametre sayısını denetle; uyuşmazlıkta ValueError."""
        _, _, params = LOAD_TYPES[self.kind]
        if len(self.values) != len(params):
            raise ValueError(
                f"'{self.kind}' yükü {len(params)} parametre bekler "
                f"({', '.join(params)}), {len(self.values)} verildi."
            )

    def to_lm_row(self) -> list:
        if self.kind in AXIAL_KINDS:
            raise ValueError(f"'{self.kind}' eksenel yüktür; PyCBA LM satırına çevrilemez.")
        code, _, params = LOAD_TYPES[self.kind]
        vals = list(self.values)
        self.check_params()
        if self.kind == "trapezoid" and vals[2] == 0 and vals[3] == 0:
            vals = vals[:2]  # tam-açıklık trapez: [span, 5, w1, w2]
        return [self.span, code] + vals


@dataclass
class BeamModel:
    """Sürekli kiriş modeli.

    spans    : açıklık uzunlukları [m], N eleman
    EI       : her açıklığın eğilme rijitliği [kNm²], N eleman
    supports : her düğümün mesnet tipi (SUPPORT_TYPES), N+1 eleman
    loads    : yük listesi
    hinges   : iç mafsallı düğüm no'ları (1-tabanlı, yalnız ara düğümler) —
               Gerber kirişi; boş liste = tam sürekli kiriş
    """

    spans: List[float]
    EI: List[float]
    supports: List[str]
    loads: List[Load] = field(default_factory=list)
    hinges: List[int] = field(default_factory=list)

    @property
    def n_spans(self) -> int:
        return len(self.spans)

    @property
    def n_nodes(self) -> int:
        return len(self.spans) + 1

    def validate(self) -> List[str]:
        """Hata mesajları listesi döndürür; boş liste = model geçerli."""
        errors = []
        if not self.spans:
            errors.append("En az bir açıklık tanımlanmalı.")
        if any(L <= 0 for L in self.spans):
            errors.append("Tüm açıklık uzunlukları pozitif olmalı.")
        if len(self.EI) != self.n_spans:
            errors.append(
                f"EI sayısı ({len(self.EI)}) açıklık sayısına ({self.n_spans}) eşit olmalı."
            )
        if any(ei <= 0 for ei in self.EI):
            errors.append("Tüm EI değerleri pozitif olmalı.")
        if len(self.supports) != self.n_nodes:
            errors.append(
                f"Mesnet sayısı ({len(self.supports)}) düğüm sayısına "
                f"({self.n_nodes} = açıklık + 1) eşit olmalı."
            )
        for s in self.supports:
            if s not in SUPPORT_TYPES:
                errors.append(f"Bilinmeyen mesnet tipi: {s!r}")
        # Mafsal yalnız ARA düğüme konur: uç düğümde tek eleman vardır, orada
        # "mafsal" zaten mesnet tipinin (pin/roller) işidir.
        gorulen = set()
        for h in self.hinges:
            if not (2 <= h <= self.n_nodes - 1):
                errors.append(
                    f"Mafsal düğüm no {h} geçersiz: yalnız ara düğümlere "
                    f"(2..{self.n_nodes - 1}) mafsal konabilir."
                )
            elif h in gorulen:
                errors.append(f"Düğüm {h} birden fazla kez mafsal olarak verildi.")
            gorulen.add(h)
        for i, ld in enumerate(self.loads, start=1):
            if ld.kind not in LOAD_TYPES:
                errors.append(f"Yük {i}: bilinmeyen tip {ld.kind!r}")
                continue
            if not (1 <= ld.span <= self.n_spans):
                errors.append(
                    f"Yük {i}: açıklık no {ld.span} geçersiz (1..{self.n_spans})."
                )
            try:
                ld.check_params()
            except ValueError as e:
                errors.append(f"Yük {i}: {e}")
                continue
            if 1 <= ld.span <= self.n_spans:
                pos_err = check_load_position(
                    ld.kind, ld.values, self.spans[ld.span - 1]
                )
                if pos_err:
                    errors.append(f"Yük {i}: {pos_err}")
        return errors

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
        """
        r = sum({"pin": 1, "roller": 1, "fixed": 2, "free": 0}.get(s, 0)
                for s in self.supports)
        return r - len(self.hinges) - 2

    def to_pycba(self) -> dict:
        """`BeamAnalysis(**model.to_pycba())` ile doğrudan kullanılabilir sözlük."""
        errors = self.validate()
        if errors:
            raise ValueError(" / ".join(errors))
        # Eksenel yükler PyCBA'ya gitmez (core/axial.py çözer); LM boş kalırsa
        # None geçilir — PyCBA boş yük matrisiyle sıfır sonuç üretir.
        lm = [ld.to_lm_row() for ld in self.loads if ld.kind not in AXIAL_KINDS]
        return {
            "L": list(self.spans),
            "EI": list(self.EI),
            "supports": list(self.supports),
            "LM": lm or None,
            "eletype": self.eletypes(),
        }
