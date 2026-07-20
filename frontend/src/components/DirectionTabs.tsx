import clsx from "clsx";
import { Swords, Shield, Star, Search } from "lucide-react";
import type { Direction } from "../types";

const TABS: { key: Direction; label: string; icon: React.ElementType }[] = [
  { key: "推荐阵容", label: "推荐阵容", icon: Swords },
  { key: "推荐装备", label: "推荐装备", icon: Shield },
  { key: "查专属", label: "查专属", icon: Star },
  { key: "检索装备", label: "检索装备", icon: Search },
];

interface DirectionTabsProps {
  value: Direction | undefined;
  onChange: (d: Direction) => void;
}

export default function DirectionTabs({ value, onChange }: DirectionTabsProps) {
  return (
    <div className="flex items-center gap-1 border-t border-tft-border bg-tft-card px-2 py-2">
      {TABS.map(({ key, label, icon: Icon }) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          className={clsx(
            "flex flex-1 flex-col items-center gap-1 rounded-lg px-2 py-2 text-xs transition-colors",
            value === key
              ? "text-tft-gold border-b-2 border-tft-gold"
              : "text-gray-400 hover:text-gray-200 border-b-2 border-transparent"
          )}
        >
          <Icon size={18} />
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}
