export function brl(v: number, digits = 2): string {
  return v.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function num(v: number, digits = 2): string {
  return v.toLocaleString("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function pct(v: number, digits = 1): string {
  const s = v.toLocaleString("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return `${v > 0 ? "+" : ""}${s}%`;
}
