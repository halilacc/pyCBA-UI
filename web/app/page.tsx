"use client";

import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import Diyagram from "@/components/Diyagram";
import Num from "@/components/Num";
import { analizEt, metaGetir, type Analiz, type Girdi, type Meta, type Yuk } from "@/lib/api";
import { bicim, sayi } from "@/lib/i18n";

// Kaynak bağlantıları: AGPL 13. madde gereği çalışan uygulamada bulunmak zorunda.
const KAYNAK_URL = "https://github.com/halilacc/pyCBA-UI";
const GELISTIRICI = "Halil Reis Acir";
const LINKEDIN_URL = "https://www.linkedin.com/in/halil-reis-acir";

const ORNEK: Yuk[] = [
  { span: 1, kind: "udl", values: [20] },
  { span: 2, kind: "udl", values: [20] },
];

const dene = <T,>(f: () => T): T | undefined => { try { return f(); } catch { return undefined; } };

function kalin(metin: string) {
  return metin.split("**").map((p, i) => (i % 2 ? <strong key={i}>{p}</strong> : <Fragment key={i}>{p}</Fragment>));
}

export default function Sayfa() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [dil, setDil] = useState("tr");
  const [gece, setGece] = useState(false);

  const [n, setN] = useState(2);
  const [spans, setSpans] = useState<number[]>([6, 6]);
  const [EI, setEI] = useState<number[]>([30000, 30000]);
  const [supports, setSupports] = useState<string[]>(["pin", "roller", "pin"]);
  const [springs, setSprings] = useState<Record<number, number>>({});
  const [hinges, setHinges] = useState<number[]>([]);
  const [spanHinges, setSpanHinges] = useState<[number, number][]>([]);
  const [cokme, setCokme] = useState<Record<number, number>>({});
  const [loads, setLoads] = useState<Yuk[]>(ORNEK);
  const [goster, setGoster] = useState({ sema: true, N: true, V: true, M: true, D: true });
  const [dusenler, setDusenler] = useState<string | null>(null);

  // ekleme formları
  const [ySpan, setYSpan] = useState(1);
  const [yKind, setYKind] = useState("udl");
  const [yDeger, setYDeger] = useState<Record<string, number | null>>({});
  const [yHata, setYHata] = useState<string | null>(null);
  const [mhSpan, setMhSpan] = useState(1);
  const [mhA, setMhA] = useState<number | null>(null);
  const [mhHata, setMhHata] = useState<string | null>(null);

  const [analiz, setAnaliz] = useState<Analiz | null>(null);
  const [bekliyor, setBekliyor] = useState(true);
  const [sunucuHata, setSunucuHata] = useState(false);

  // ------------------------------------------------------------- başlangıç
  useEffect(() => {
    metaGetir().then(setMeta).catch(() => setSunucuHata(true));
    const d = dene(() => localStorage.getItem("dil"));
    if (d) setDil(d);
    const g = dene(() => localStorage.getItem("tema"));
    setGece(g ? g === "gece" : window.matchMedia("(prefers-color-scheme: dark)").matches);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.tema = gece ? "gece" : "aydinlik";
    document.documentElement.lang = dil;
    dene(() => { localStorage.setItem("tema", gece ? "gece" : "aydinlik"); localStorage.setItem("dil", dil); });
  }, [gece, dil]);

  const t = (k: string, kw: Record<string, number | string> = {}) =>
    bicim(meta?.metinler[dil]?.[k] ?? meta?.metinler.tr?.[k] ?? k, kw);

  // ------------------------------------------------------------- hesap
  const girdi: Girdi = useMemo(() => ({
    spans, EI, supports, loads, hinges,
    span_hinges: spanHinges,
    springs: Object.fromEntries(Object.entries(springs).filter(([k]) => supports[Number(k) - 1] === "spring")),
    settlements_mm: Object.fromEntries(Object.entries(cokme).filter(([k, v]) =>
      v !== 0 && !["free", "spring"].includes(supports[Number(k) - 1]))),
    dil,
  }), [spans, EI, supports, loads, hinges, spanHinges, springs, cokme, dil]);

  const sonIstek = useRef<AbortController | null>(null);
  useEffect(() => {
    if (!meta) return;
    setBekliyor(true);
    const zaman = setTimeout(() => {
      sonIstek.current?.abort();
      const ac = (sonIstek.current = new AbortController());
      analizEt(girdi, ac.signal)
        .then((a) => { setAnaliz(a); setSunucuHata(false); setBekliyor(false); })
        .catch((e) => { if (e.name !== "AbortError") { setSunucuHata(true); setBekliyor(false); } });
    }, 200);
    return () => clearTimeout(zaman);
  }, [girdi, meta]);

  if (!meta) {
    return <div className="bos">{sunucuHata ? "⚠️ API: /api/meta" : "…"}</div>;
  }

  // ------------------------------------------------------------- değiştiriciler
  const aciklikSayisi = (yeni: number) => {
    const m = Math.min(10, Math.max(1, Math.round(yeni)));
    if (m === n) return;
    const boyla = <T,>(a: T[], len: number, v: T) => Array.from({ length: len }, (_, i) => a[i] ?? v);
    const gerberDusen = hinges.filter((h) => h > m);
    const icDusen = spanHinges.filter(([s]) => s > m).length;
    setSpans(boyla(spans, m, 6)); setEI(boyla(EI, m, 30000));
    setSupports(Array.from({ length: m + 1 }, (_, i) => supports[i] ?? (i === m ? "pin" : "roller")));
    setHinges(hinges.filter((h) => h <= m));
    setSpanHinges(spanHinges.filter(([s]) => s <= m));
    setN(m);
    setYSpan((s) => Math.min(s, m)); setMhSpan((s) => Math.min(s, m));
    const parca = [
      gerberDusen.length ? t("mafsal.gerber_dustu", { dugumler: gerberDusen.join(", ") }) : "",
      icDusen ? t("mafsal.dustu", { n: icDusen }) : "",
    ].filter(Boolean);
    setDusenler(parca.length ? parca.join(" ") : null);
  };
  const guncelle = <T,>(a: T[], i: number, v: T) => a.map((x, j) => (j === i ? v : x));
  const dilBirim = (p: string) => meta.param_units[p];

  const yeniYukTipi = meta.load_types[yKind];
  const ekleYuk = () => {
    const values = yeniYukTipi.params.map((p) => yDeger[p] ?? 0);
    const siddet = values.filter((_, i) => !["a", "c"].includes(yeniYukTipi.params[i]));
    if (siddet.every((v) => Math.abs(v) < 1e-12)) { setYHata(t("yuk.siddet_sifir")); return; }
    setYHata(null);
    setLoads([...loads, { span: ySpan, kind: yKind, values }]);
    setYDeger({});
  };
  const ekleMafsal = () => {
    const L = spans[mhSpan - 1], a = mhA ?? 0;
    if (!(a > 0 && a < L)) { setMhHata(t("mafsal.konum_hatasi", { L })); return; }
    if (spanHinges.some(([s, x]) => s === mhSpan && x === a)) { setMhHata(t("mafsal.zaten_var")); return; }
    setMhHata(null); setSpanHinges([...spanHinges, [mhSpan, a]]); setMhA(null);
  };

  // ------------------------------------------------------------- sunum yardımcıları
  const s = analiz?.sonuc ?? null;
  const csv = (basliklar: string[], ...diziler: number[][]) =>
    [basliklar.join(","), ...diziler[0].map((_, i) => diziler.map((d) => Number(d[i].toPrecision(6))).join(","))].join("\n") + "\n";
  const indir = (ad: string, icerik: string) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([icerik], { type: "text/csv" }));
    a.download = ad; a.click(); URL.revokeObjectURL(a.href);
  };
  const kart = (anahtar: string, birim: string, x: number[], y: number[], olcek = 1) => {
    const vmaks = Math.max(...y), vmin = Math.min(...y);
    const xMaks = x[y.indexOf(vmaks)], xMin = x[y.indexOf(vmin)];
    const bicimle = (v: number) => sayi(v * olcek + 0);
    const maksBaskin = Math.abs(vmaks) >= Math.abs(vmin);
    const [baslik, deger, xd, alt, altDeger, xa] = maksBaskin
      ? ["kart.maks", vmaks, xMaks, "kart.min", vmin, xMin]
      : ["kart.min_baslik", vmin, xMin, "kart.maks_alt", vmaks, xMaks];
    return (
      <div className="metrik" key={anahtar}>
        <div className="ad">{t(baslik as string, { ad: t(`buyukluk.${anahtar}`), birim })}</div>
        <div className="deger">{bicimle(deger as number)}</div>
        <div className="alt">{t("kart.konum", { x: xd as number })}<br />
          {t(alt as string, { deger: bicimle(altDeger as number), x: xa as number })}</div>
      </div>
    );
  };

  const hataVar = !!analiz?.hatalar.length;

  return (
    <>
      <header className="ust">
        <div className="marka">
          <span className="goz">{t("hero.eyebrow")}</span>
          <h1>{t("hero.baslik")}</h1>
        </div>
        <label className="onay">
          <input type="checkbox" checked={gece} onChange={(e) => setGece(e.target.checked)} />
          {t("gece_modu")}
        </label>
        <select aria-label={t("dil_secimi")} value={dil} onChange={(e) => setDil(e.target.value)}>
          {Object.entries(meta.diller).map(([k, ad]) => <option key={k} value={k}>{ad}</option>)}
        </select>
      </header>

      <div className="duzen">
        <aside className="yan">
          {/* 1. Geometri */}
          <section className="bolum">
            <h2>{t("bolum.geometri")}</h2>
            <label className="alan">{t("aciklik_sayisi")}
              <Num label={t("aciklik_sayisi")} value={n} min={1} max={10} onChange={(v) => v !== null && aciklikSayisi(v)} />
            </label>
            {spans.map((L, i) => (
              <div className="cift" key={i}>
                <label className="alan">L{i + 1} [m]
                  <Num label={`L${i + 1} [m]`} value={L} min={0.1} step={0.5} onChange={(v) => v !== null && setSpans(guncelle(spans, i, v))} />
                </label>
                <label className="alan">EI{i + 1} [kNm²]
                  <Num label={`EI${i + 1}`} value={EI[i]} min={1} step={1000} onChange={(v) => v !== null && setEI(guncelle(EI, i, v))} />
                </label>
              </div>
            ))}
          </section>

          {/* 2. Mesnetler */}
          <section className="bolum">
            <h2>{t("bolum.mesnetler")}</h2>
            {supports.map((sup, i) => (
              <Fragment key={i}>
                <label className="alan">{t("dugum_no", { n: i + 1 })}
                  <select value={sup} onChange={(e) => {
                    setSupports(guncelle(supports, i, e.target.value));
                    if (e.target.value === "spring") setSprings({ ...springs, [i + 1]: springs[i + 1] ?? 10000 });
                  }}>
                    {meta.support_types.map((k) => <option key={k} value={k}>{t(`mesnet.${k}`)}</option>)}
                  </select>
                </label>
                {sup === "spring" && (
                  <label className="alan" title={t("yay.yardim")}>{t("yay.katsayi", { n: i + 1 })}
                    <Num label={t("yay.katsayi", { n: i + 1 })} value={springs[i + 1] ?? 10000} min={0.01} step={1000}
                      onChange={(v) => v !== null && setSprings({ ...springs, [i + 1]: v })} />
                  </label>
                )}
              </Fragment>
            ))}
            {n > 1 && (
              <div className="alan">{t("mafsal.coklu_secim")}
                <div className="cipler" title={t("mafsal.yardim")}>
                  {Array.from({ length: n - 1 }, (_, k) => k + 2).map((h) => (
                    <label className="onay" key={h}>
                      <input type="checkbox" checked={hinges.includes(h)}
                        onChange={(e) => setHinges(e.target.checked ? [...hinges, h].sort() : hinges.filter((x) => x !== h))} />
                      {t("dugum_no", { n: h })}
                    </label>
                  ))}
                </div>
              </div>
            )}
            <details>
              <summary>{t("mafsal.baslik")}</summary>
              <div className="ic">
                <p className="not">{t("mafsal.aciklama")}</p>
                <label className="alan">{t("mafsal.aciklik_no")}
                  <Num label={t("mafsal.aciklik_no")} value={mhSpan} min={1} max={n} onChange={(v) => v !== null && setMhSpan(Math.min(n, Math.max(1, Math.round(v))))} />
                </label>
                <label className="alan">{t("mafsal.konum", { L: spans[mhSpan - 1] })}
                  <Num label={t("mafsal.konum", { L: spans[mhSpan - 1] })} value={mhA} placeholder="0" min={0} max={spans[mhSpan - 1]} step={0.25} onChange={setMhA} />
                </label>
                <button type="button" onClick={ekleMafsal}>{t("mafsal.ekle")}</button>
                {mhHata && <div className="bildirim hata" role="alert">{mhHata}</div>}
                {spanHinges.map(([sp, a], j) => (
                  <div className="cift" key={j}>
                    <span>{t("mafsal.satir", { sp, a })}</span>
                    <button type="button" className="hayalet" title={t("mafsal.sil_yardim", { sp, a })}
                      onClick={() => setSpanHinges(spanHinges.filter((_, k) => k !== j))}>{t("liste.sil")}</button>
                  </div>
                ))}
              </div>
            </details>
            <details>
              <summary>{t("cokme.baslik")}</summary>
              <div className="ic">
                <p className="not">{t("cokme.aciklama")}</p>
                {supports.every((x) => x === "free" || x === "spring") && <p className="not">{t("cokme.mesnet_yok")}</p>}
                {supports.map((sup, i) => sup === "free" || sup === "spring" ? null : (
                  <label className="alan" key={i} title={t("cokme.yardim")}>{t("cokme.alan", { n: i + 1 })}
                    <Num label={t("cokme.alan", { n: i + 1 })} value={cokme[i + 1] ?? 0} step={1}
                      onChange={(v) => v !== null && setCokme({ ...cokme, [i + 1]: v })} />
                  </label>
                ))}
              </div>
            </details>
            {dusenler && <div className="bildirim uyari" role="status">{dusenler}</div>}
          </section>

          {/* 3. Yükler */}
          <section className="bolum">
            <h2>{t("bolum.yukler")}</h2>
            <label className="alan">{t("aciklik_no")}
              <Num label={t("aciklik_no")} value={ySpan} min={1} max={n} onChange={(v) => v !== null && setYSpan(Math.min(n, Math.max(1, Math.round(v))))} />
            </label>
            <label className="alan">{t("yuk_tipi")}
              <select value={yKind} onChange={(e) => { setYKind(e.target.value); setYDeger({}); setYHata(null); }}>
                {Object.keys(meta.load_types).map((k) => <option key={k} value={k}>{t(`yuk.${k}`)}</option>)}
              </select>
            </label>
            <p className="not">{t(`ipucu.${yKind}`)} {t("secili_aciklik", { L: spans[ySpan - 1] })}</p>
            {yeniYukTipi.params.map((p) => (
              <label className="alan" key={`${yKind}-${p}`}>{t(`param.${p}`)} [{dilBirim(p)}]
                <Num label={t(`param.${p}`)} value={yDeger[p] ?? null} placeholder="0" step={p === "a" || p === "c" ? 0.25 : 1}
                  min={p === "a" || p === "c" ? 0 : undefined} max={p === "a" || p === "c" ? spans[ySpan - 1] : undefined}
                  onChange={(v) => setYDeger({ ...yDeger, [p]: v })} />
              </label>
            ))}
            <button type="button" className="birincil" onClick={ekleYuk}>{t("yuk.ekle")}</button>
            {yHata && <div className="bildirim hata" role="alert">{yHata}</div>}
          </section>

          {/* 4. Görünüm */}
          <section className="bolum">
            <h2>{t("bolum.gorunum")}</h2>
            <p className="not">{t("gorunum.aciklama")}</p>
            {([["sema", "gorunum.sema"], ["N", "gorunum.N"], ["V", "gorunum.V"], ["M", "gorunum.M"], ["D", "gorunum.D"]] as const)
              .filter(([k]) => k !== "N" || s?.has_axial)
              .map(([k, etiket]) => (
                <label className="onay" key={k}>
                  <input type="checkbox" checked={goster[k]} onChange={(e) => setGoster({ ...goster, [k]: e.target.checked })} />
                  {t(etiket)}
                </label>
              ))}
          </section>

          <footer className="alt-bilgi">
            <a href={KAYNAK_URL} target="_blank" rel="noopener noreferrer">{t("lisans.kaynak")}</a>
            <span>{t("lisans.atif")}</span>
            <span>{t("lisans.gelistiren")} <a href={LINKEDIN_URL} target="_blank" rel="noopener noreferrer">{GELISTIRICI}</a></span>
          </footer>
        </aside>

        <main className="ana" aria-busy={bekliyor}>
          {sunucuHata && <div className="bildirim hata" role="alert">{t("web.baglanti_hatasi")}</div>}

          {/* Yük listesi */}
          <section className="kart">
            <h2>{t("liste.baslik")}</h2>
            {loads.length === 0 ? <p className="not">{t("liste.bos")}</p> : (
              <>
                {JSON.stringify(loads) === JSON.stringify(ORNEK) && <p className="not">{t("liste.ornek")}</p>}
                {loads.map((ld, i) => (
                  <div className="yuk" key={i}>
                    <div className="ad">
                      <span>{i + 1}. {t(`yuk.${ld.kind}`)}</span>
                      <button type="button" className="hayalet" title={t("liste.sil_yardim")}
                        onClick={() => setLoads(loads.filter((_, j) => j !== i))}>{t("liste.sil")}</button>
                    </div>
                    <div className="alanlar">
                      <label>{t("aciklik_no")}
                        <Num label={t("aciklik_no")} value={ld.span} min={1} max={n}
                          onChange={(v) => v !== null && setLoads(guncelle(loads, i, { ...ld, span: Math.round(v) }))} />
                      </label>
                      {meta.load_types[ld.kind].params.map((p, j) => (
                        <label key={p}>{p} [{dilBirim(p)}]
                          <Num label={`${t(`param.${p}`)} [${dilBirim(p)}]`} value={ld.values[j]}
                            onChange={(v) => v !== null && setLoads(guncelle(loads, i, { ...ld, values: guncelle(ld.values, j, v) }))} />
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </>
            )}
          </section>

          {analiz?.hatalar.map((h, i) => <div className="bildirim hata" role="alert" key={i}>{h}</div>)}

          {goster.sema && analiz?.sema_svg && (
            <section className="kart">
              <h2>{t("sema.baslik")}</h2>
              {/* SVG kendi sunucumuzun matplotlib çıktısıdır (kullanıcı metni içermez). */}
              <div className="sema" role="img" aria-label={t("sema.aria")} dangerouslySetInnerHTML={{ __html: analiz.sema_svg }} />
            </section>
          )}

          {!hataVar && analiz && !s && <p className="not">{t("sonuclar.yuk_ekleyin")}</p>}

          {s && !hataVar && (
            <>
              <h2>{t("sonuclar.baslik")}</h2>
              {s.ea_uyari && <div className="bildirim uyari">{t("uyari.ea")}</div>}
              {s.has_settlements && s.static_degree === 0 && <div className="bildirim uyari">{t("uyari.cokme_izostatik")}</div>}
              <div className="metrikler">
                {kart("moment", "kNm", s.x, s.M)}
                {kart("kesme", "kN", s.x, s.V)}
                {kart("sehim", "mm", s.x, s.D, 1000)}
                {s.has_axial && kart("normal", "kN", s.xN, s.N)}
              </div>

              <section className="kart">
                <Diyagram sonuc={s} gorunum={goster} karanlik={gece} normalYesil={meta.normal_kuvvet_yesili} t={(k) => t(k)} />
                <p>
                  <button type="button" onClick={() => indir(t("csv.diyagram_dosya"),
                    csv([t("csv.x"), t("csv.moment"), t("csv.kesme"), t("csv.sehim")], s.x, s.M, s.V, s.D.map((d) => d * 1000)))}>
                    {t("csv.diyagram_buton")}
                  </button>{" "}
                  {s.has_axial && (
                    <button type="button" onClick={() => indir(t("csv.normal_dosya"),
                      csv([t("csv.x"), t("csv.normal")], s.xN, s.N))}>{t("csv.normal_buton")}</button>
                  )}
                </p>
              </section>

              <section className="kart">
                <h2>{t("tepki.baslik")}</h2>
                <div className="tablo">
                  <table>
                    <thead>
                      <tr>
                        <th>{t("tepki.dugum")}</th><th>{t("tepki.konum")}</th><th>{t("tepki.dusey")}</th>
                        {s.has_axial && <th>{t("tepki.yatay")}</th>}
                        {s.has_fixed && <th>{t("tepki.moment")}</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {s.reactions.map((r) => (
                        <tr key={r.node}>
                          <td>{r.node}</td><td>{r.x.toFixed(3)}</td>
                          <td>{r.V === null ? "—" : sayi(r.V, 3)}</td>
                          {s.has_axial && <td>{r.H === null ? "—" : sayi(r.H, 3)}</td>}
                          {s.has_fixed && <td>{r.M === null ? "—" : sayi(r.M, 3)}</td>}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <details style={{ marginTop: 12 }}>
                  <summary>{t("tepki.isaret_baslik")}</summary>
                  <div className="ic"><p className="not">{kalin(t("tepki.isaret"))}</p></div>
                </details>
              </section>
            </>
          )}
        </main>
      </div>
    </>
  );
}
