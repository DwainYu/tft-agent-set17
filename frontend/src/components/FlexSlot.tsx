import type { FlexSlotData } from "../types";

interface FlexSlotProps {
  data: FlexSlotData | null;
}

export default function FlexSlot({ data }: FlexSlotProps) {
  if (!data) return null;

  return (
    <div className="rounded-lg border border-dashed border-tft-border bg-tft-dark/30 px-3 py-2 text-sm">
      <span className="text-gray-400">灵活位：</span>
      <span className="text-gray-200">
        {data.population != null && (
          <span className="mr-1.5 font-mono text-tft-gold">{data.population}人口</span>
        )}
        {data.champion && <span>{data.champion}</span>}
      </span>
    </div>
  );
}
