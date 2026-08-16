import clsx from "clsx";
import type { ItemDelta } from "../types";
import ItemIcon from "./ItemIcon";

interface EmblemBlockProps {
  items: ItemDelta[];
}

export default function EmblemBlock({ items }: EmblemBlockProps) {
  if (items.length === 0) return null;

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
        纹章推荐
      </h4>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li
            key={i}
            className="flex items-center gap-2 rounded bg-tft-dark/40 px-2.5 py-1.5 text-sm"
          >
            {item.item_id && <ItemIcon name={item.item_id} size={24} />}
            <div className="min-w-0 flex-1">
              <span className="text-gray-200">{item.name_zh}</span>
              {item.target && (
                <span className="ml-1.5 text-xs text-gray-500">
                  → {item.target}
                </span>
              )}
            </div>
            <span
              className={clsx(
                "ml-2 shrink-0 text-xs font-mono",
                item.delta < 0 ? "text-green-400" : "text-red-400"
              )}
            >
              {item.delta > 0 ? "+" : ""}
              {item.delta}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
