// API sözleşmesi (api/index.py ile birebir). Birimler çekirdekle aynı:
// kN, m, kNm²; sehim D metre; çökme yalnız burada mm ve AŞAĞI POZİTİF.

export type Meta = {
  load_types: Record<string, { params: string[]; axial: boolean }>;
  support_types: string[];
  param_units: Record<string, string>;
  diller: Record<string, string>;
  varsayilan_dil: string;
  metinler: Record<string, Record<string, string>>;
  normal_kuvvet_yesili: string;
};

export type Yuk = { span: number; kind: string; values: number[] };

export type Girdi = {
  spans: number[];
  EI: number[];
  supports: string[];
  loads: Yuk[];
  hinges: number[];
  span_hinges: [number, number][];
  springs: Record<number, number>;
  settlements_mm: Record<number, number>;
  dil: string;
};

export type Tepki = {
  node: number; x: number; V: number | null; M: number | null; H: number | null;
};

export type Sonuc = {
  x: number[]; M: number[]; V: number[]; D: number[];
  xN: number[]; N: number[];
  ea_uyari: boolean;
  reactions: Tepki[];
  has_axial: boolean; has_fixed: boolean;
  static_degree: number;
  node_x: number[]; supports: string[];
  has_settlements: boolean;
};

export type Analiz = { hatalar: string[]; sema_svg: string | null; sonuc: Sonuc | null };

export async function metaGetir(): Promise<Meta> {
  const r = await fetch("/api/meta");
  if (!r.ok) throw new Error(`meta ${r.status}`);
  return r.json();
}

export async function analizEt(g: Girdi, signal: AbortSignal): Promise<Analiz> {
  const r = await fetch("/api/analiz", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(g), signal,
  });
  if (!r.ok) throw new Error(`analiz ${r.status}`);
  return r.json();
}
