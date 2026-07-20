import { useState } from "react";
import clsx from "clsx";
import type { ChampionInfo } from "../types";

const COST_COLORS: Record<number, string> = {
  1: "bg-gray-500",
  2: "bg-green-500",
  3: "bg-blue-500",
  4: "bg-purple-500",
  5: "bg-tft-gold",
};

const COST_TEXT: Record<number, string> = {
  1: "text-gray-100",
  2: "text-green-100",
  3: "text-blue-100",
  4: "text-purple-100",
  5: "text-tft-dark",
};

interface HeroAvatarProps {
  champion: ChampionInfo;
}

export default function HeroAvatar({ champion }: HeroAvatarProps) {
  const [imgError, setImgError] = useState(false);
  const showFallback = !champion.icon || imgError;
  const costColor = COST_COLORS[champion.cost] ?? "bg-gray-500";
  const costText = COST_TEXT[champion.cost] ?? "text-white";

  return (
    <div className="flex w-14 flex-col items-center gap-1">
      {/* Avatar */}
      <div className="relative">
        {showFallback ? (
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-tft-border text-lg font-bold text-white">
            {champion.name_zh.charAt(0)}
          </div>
        ) : (
          <img
            src={champion.icon!}
            alt={champion.name_zh}
            className="h-12 w-12 rounded-lg object-cover"
            onError={() => setImgError(true)}
          />
        )}

        {/* Cost badge */}
        <span
          className={clsx(
            "absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold",
            costColor,
            costText
          )}
        >
          {champion.cost}
        </span>
      </div>

      {/* Name */}
      <span className="w-full truncate text-center text-[10px] text-gray-300">
        {champion.name_zh}
      </span>
    </div>
  );
}
