"use client";

import { useEffect, useState } from "react";

type Props = {
  value: number | null;
  onChange: (v: number | null) => void;
  min?: number; max?: number; step?: number;
  placeholder?: string; label: string; id?: string;
};

// Yazarken ara durumlar ("", "-", "1.") geçerli sayı değildir; taslak metin yerel
// tutulur, yalnız geçerli sayı yukarı verilir. Boş alan null'dır (ekleme
// formunda placeholder "0", Streamlit sürümüyle aynı).
export default function Num({ value, onChange, min, max, step = 1, placeholder, label, id }: Props) {
  const [taslak, setTaslak] = useState(value === null ? "" : String(value));
  useEffect(() => {
    setTaslak((t) => (Number(t) === value && t !== "" ? t : value === null ? "" : String(value)));
  }, [value]);
  return (
    <input
      id={id} aria-label={label} type="number" inputMode="decimal"
      value={taslak} min={min} max={max} step={step} placeholder={placeholder}
      onChange={(e) => {
        setTaslak(e.target.value);
        if (e.target.value === "") onChange(null);
        else if (!Number.isNaN(e.target.valueAsNumber)) onChange(e.target.valueAsNumber);
      }}
    />
  );
}
