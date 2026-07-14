// Segmentos (commodities) e o mapeamento produto -> segmento. Espelha o backend.
// `disabled` = commodity exibida como opção, mas ainda sem dados (ex.: açúcar).

export const SEGMENTS = [
  { key: "fertilizante", label: "Fertilizante", disabled: false },
  { key: "grão", label: "Grãos", disabled: false },
  { key: "algodão", label: "Algodão", disabled: false },
  { key: "açúcar", label: "Açúcar", disabled: true },
] as const;

export type SegmentKey = (typeof SEGMENTS)[number]["key"];

const MAP: Record<string, SegmentKey> = {};
for (const p of ["ureia", "map", "kcl", "cloreto", "npk", "fertilizante", "nitrato"])
  MAP[p] = "fertilizante";
for (const p of ["soja", "milho", "sorgo", "trigo", "grão", "grao"]) MAP[p] = "grão";
for (const p of ["algodão", "algodao"]) MAP[p] = "algodão";
// açúcar: sem produtos mapeados ainda (sem dados) — botão fica desabilitado.

export function segmentOf(produto: string): SegmentKey | null {
  return MAP[produto.trim().toLowerCase()] ?? null;
}
