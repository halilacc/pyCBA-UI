"use client";

import { useEffect, useRef } from "react";
import type { Sonuc } from "@/lib/api";
import { sayi } from "@/lib/i18n";

// Streamlit sürümüyle (app.py) aynı konvansiyonlar: Normal · Kesme · Moment ·
// Sehim sırası, moment ekseni ters (sagging aşağıda), mesnet çizgileri harfli,
// her panelde maks/min işareti ve konumuyla.
const KIRMIZI = "#d62728";
const KIRMIZI_DOLGU = "rgba(214,39,40,0.12)";

type Panel = {
  ad: string; birim: string; x: number[]; y: number[];
  renk: string; dolgu: string | null; ters: boolean;
};

function etiketSayi(v: number): string {
  if (v === 0) return sayi(0);
  return Math.abs(v) >= 1 ? sayi(v) : Number(v.toPrecision(4)).toString();
}

export type Gorunum = { N: boolean; V: boolean; M: boolean; D: boolean };

type Props = {
  sonuc: Sonuc;
  gorunum: Gorunum;
  karanlik: boolean;
  normalYesil: string;
  t: (k: string) => string;
};

export default function Diyagram({ sonuc, gorunum, karanlik, normalYesil, t }: Props) {
  const kap = useRef<HTMLDivElement>(null);

  const paneller: Panel[] = [];
  if (sonuc.has_axial && gorunum.N)
    paneller.push({ ad: t("panel.normal"), birim: "kN", x: sonuc.xN, y: sonuc.N,
      renk: normalYesil, dolgu: "rgba(44,160,44,0.15)", ters: false });
  if (gorunum.V)
    paneller.push({ ad: t("panel.kesme"), birim: "kN", x: sonuc.x, y: sonuc.V,
      renk: KIRMIZI, dolgu: KIRMIZI_DOLGU, ters: false });
  if (gorunum.M)
    paneller.push({ ad: t("panel.moment"), birim: "kNm", x: sonuc.x, y: sonuc.M,
      renk: KIRMIZI, dolgu: KIRMIZI_DOLGU, ters: true });
  if (gorunum.D)
    paneller.push({ ad: t("panel.sehim"), birim: "mm", x: sonuc.x,
      y: sonuc.D.map((d) => d * 1000), renk: KIRMIZI, dolgu: null, ters: false });

  const anahtar = JSON.stringify([paneller.map((p) => p.ad), karanlik, t("diyagram.baslik")]);

  useEffect(() => {
    const el = kap.current;
    if (!el || paneller.length === 0) return;
    let iptal = false;
    (async () => {
      const Plotly = (await import("plotly.js-basic-dist-min")).default;
      if (iptal) return;
      const yazi = karanlik ? "#E9E7E2" : "#1C1B19";
      const izgara = karanlik ? "rgba(255,255,255,0.10)" : "rgba(28,27,25,0.08)";
      const sifir = karanlik ? "rgba(233,231,226,0.55)" : "rgba(28,27,25,0.45)";
      const mesnet = karanlik ? "rgba(255,255,255,0.22)" : "rgba(28,27,25,0.18)";
      const halka = karanlik ? "#1E2028" : "#FFFFFF";
      const n = paneller.length;
      const bosluk = 0.05;
      const yukseklik = (1 - bosluk * (n - 1)) / n;

      const veri: object[] = [];
      const notlar: object[] = [];
      const layout: Record<string, unknown> = {
        title: { text: t("diyagram.baslik"), y: 0.99, yanchor: "top", font: { color: yazi } },
        margin: { t: 70, l: 70, r: 20, b: 50 },
        height: 240 * n + 90,
        showlegend: false,
        paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: yazi },
        separators: ". ",
        xaxis: { anchor: `y${n === 1 ? "" : n}`, title: { text: t("diyagram.eksen_x") },
          gridcolor: izgara, zerolinecolor: sifir, linecolor: izgara, fixedrange: true,
          tickfont: { color: yazi }, title_font: { color: yazi } },
        shapes: [],
        annotations: notlar,
      };
      const sekiller = layout.shapes as object[];

      paneller.forEach((p, i) => {
        const k = i + 1;
        const ust = 1 - i * (yukseklik + bosluk);
        const ek = k === 1 ? "" : String(k);
        layout[`yaxis${ek}`] = {
          domain: [ust - yukseklik, ust], anchor: "x",
          title: { text: `${p.ad} [${p.birim}]` },
          gridcolor: izgara, zerolinecolor: sifir, fixedrange: true,
          tickfont: { color: yazi }, title_font: { color: yazi },
          ...(p.ters ? { autorange: "reversed" } : {}),
        };
        veri.push({
          x: p.x, y: p.y, type: "scatter", mode: "lines", name: p.ad,
          xaxis: "x", yaxis: `y${ek}`,
          line: { color: p.renk, width: 1.6 },
          ...(p.dolgu ? { fill: "tozeroy", fillcolor: p.dolgu } : {}),
          hovertemplate: `${p.ad}: %{y:,.4g} ${p.birim}<extra></extra>`,
        });

        // Ekstrem işaretleri: tek işaretli diyagramda sıfır uç ve tekrar atlanır.
        const olcek = Math.max(...p.y.map(Math.abs));
        if (olcek < 1e-9) return;
        const boy = p.x[p.x.length - 1] || 1;
        const goruldu = new Set<number>();
        const iMaks = p.y.indexOf(Math.max(...p.y));
        const iMin = p.y.indexOf(Math.min(...p.y));
        for (const [idx, ustEkstrem] of [[iMaks, true], [iMin, false]] as const) {
          const deger = p.y[idx];
          if (goruldu.has(idx) || Math.abs(deger) < 0.02 * olcek) continue;
          goruldu.add(idx);
          const xe = p.x[idx];
          veri.push({
            x: [xe], y: [deger], type: "scatter", mode: "markers", showlegend: false,
            xaxis: "x", yaxis: `y${ek}`, hoverinfo: "skip",
            marker: { color: p.renk, size: 8, line: { color: halka, width: 1.6 } },
          });
          notlar.push({
            x: xe, y: deger, xref: "x", yref: `y${ek}`, showarrow: false,
            text: `${etiketSayi(deger)} ${p.birim} · ${xe.toFixed(2)} m`,
            // yshift ekran pikselidir: ters eksende "üst" ekranda alta düşer.
            yshift: (ustEkstrem ? 16 : -16) * (p.ters ? -1 : 1),
            xanchor: xe < 0.12 * boy ? "left" : xe > 0.88 * boy ? "right" : "center",
            font: { color: yazi, size: 10 }, bgcolor: halka, borderpad: 2, opacity: 0.92,
          });
        }
      });

      // Mesnet çizgileri + harfler (şemayla aynı: free düğümler atlanır).
      let harf = 0;
      sonuc.node_x.forEach((xm, j) => {
        if (sonuc.supports[j] === "free") return;
        sekiller.push({ type: "line", xref: "x", yref: "paper", x0: xm, x1: xm, y0: 0, y1: 1,
          line: { color: mesnet, width: 1, dash: "dot" } });
        notlar.push({ x: xm, y: 1, xref: "x", yref: "paper", yanchor: "bottom", yshift: 2,
          text: String.fromCharCode(65 + harf++), showarrow: false,
          font: { color: yazi, size: 11 } });
      });

      await Plotly.react(el, veri, layout, { displayModeBar: false, responsive: true });
    })();
    return () => { iptal = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sonuc, anahtar]);

  useEffect(() => {
    const el = kap.current;
    return () => {
      if (el) import("plotly.js-basic-dist-min").then((m) => m.default.purge(el));
    };
  }, []);

  if (paneller.length === 0)
    return <p className="not">{t("diyagram.hepsi_kapali")}</p>;
  return <div ref={kap} className="grafik" />;
}
