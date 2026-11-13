// Katalog API'den gelir (ui_dil.py tek kaynak). Python biçim dizgesinin
// kullanılan alt kümesini destekler: {ad}, {ad:g}, {ad:.2f}.

export type Katalog = Record<string, string>;

export function bicim(metin: string, kw: Record<string, number | string> = {}): string {
  return metin.replace(/\{(\w+)(?::([^}]*))?\}/g, (_, ad: string, f?: string) => {
    const v = kw[ad];
    if (v === undefined) return `{${ad}}`;
    const ondalik = f?.match(/^\.(\d+)f$/);
    if (ondalik) return Number(v).toFixed(Number(ondalik[1]));
    return String(v); // "g": gereksiz sıfırsız; JS sayı->metin zaten böyle
  });
}

// SI binlik ayracı (dar kırılmaz boşluk, U+202F); ondalık nokta (app.py ile aynı).
export function sayi(v: number, ondalik = 2): string {
  const s = (Math.round(v * 10 ** ondalik) / 10 ** ondalik + 0).toFixed(ondalik);
  const [tam, kesir] = s.split(".");
  return tam.replace(/\B(?=(\d{3})+(?!\d))/g, " ") + (kesir ? "." + kesir : "");
}
