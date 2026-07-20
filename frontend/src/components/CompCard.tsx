import clsx from "clsx";
import type { CompCard as CompCardType } from "../types";
import HeroAvatar from "./HeroAvatar";
import TraitBadge from "./TraitBadge";
import EmblemBlock from "./EmblemBlock";
import ArtifactBlock from "./ArtifactBlock";
import FlexSlot from "./FlexSlot";

interface CompCardProps {
  data: CompCardType;
}

export default function CompCard({ data }: CompCardProps) {
  return (
    <div className="space-y-4 rounded-xl border border-tft-border bg-tft-card p-4">
      {/* Header */}
      <div className="flex items-baseline justify-between">
        <h3 className="text-lg font-bold text-tft-gold">{data.comp_name}</h3>
        {data.avg_placement != null && (
          <span className="text-sm text-gray-400">
            平均名次{" "}
            <span
              className={clsx(
                "font-mono font-semibold",
                data.avg_placement <= 4 ? "text-green-400" : "text-gray-300"
              )}
            >
              {data.avg_placement.toFixed(2)}
            </span>
          </span>
        )}
      </div>

      {/* Champions row — horizontal scroll */}
      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin">
        {data.champions.map((c) => (
          <HeroAvatar key={c.id} champion={c} />
        ))}
      </div>

      {/* Synergies row */}
      {data.synergies.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {data.synergies.map((s) => (
            <TraitBadge key={s} name={s} />
          ))}
        </div>
      )}

      {/* Emblem + Artifact two-column grid */}
      {(data.emblems.length > 0 || data.artifacts.length > 0) && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <EmblemBlock items={data.emblems} />
          <ArtifactBlock items={data.artifacts} />
        </div>
      )}

      {/* Flex slot */}
      <FlexSlot data={data.flex_slot} />
    </div>
  );
}
