/**
 * Exporta uma tabela para CSV e dispara o download no browser.
 * Formato pt-BR: separador ";" + BOM UTF-8 (abre certo no Excel).
 * Passe números já formatados como string (ex.: "1234,56") para o Excel pt-BR
 * interpretar como número.
 */
export function downloadCsv(
  filename: string,
  headers: string[],
  rows: (string | number)[][],
): void {
  const esc = (v: string | number) => {
    const s = String(v);
    return /[";\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const body = [headers, ...rows].map((r) => r.map(esc).join(";")).join("\r\n");
  const blob = new Blob(["﻿" + body], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Número R$ no formato pt-BR sem símbolo (ex.: 1234.5 -> "1234,50"). */
export function csvNum(v: number, decimals = 2): string {
  return v.toFixed(decimals).replace(".", ",");
}
