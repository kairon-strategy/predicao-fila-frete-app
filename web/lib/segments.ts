// Segmentos (commodities) e o mapeamento produto -> segmento. Espelha o backend.

export const SEGMENTS = [
  { key: "fertilizante", label: "Fertilizante" },
  { key: "grão", label: "Grãos" },
  { key: "algodão", label: "Algodão" },
] as const;

export type SegmentKey = (typeof SEGMENTS)[number]["key"];

const MAP: Record<string, SegmentKey> = {};
for (const p of ["ureia", "map", "kcl", "cloreto", "npk", "fertilizante", "nitrato"])
  MAP[p] = "fertilizante";
for (const p of ["soja", "milho", "sorgo", "trigo", "grão", "grao"]) MAP[p] = "grão";
for (const p of ["algodão", "algodao"]) MAP[p] = "algodão";

export function segmentOf(produto: string): SegmentKey | null {
  return MAP[produto.trim().toLowerCase()] ?? null;
}
