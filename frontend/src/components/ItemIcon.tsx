import { useState } from "react";

interface ItemIconProps {
  name: string;
  size?: number;
}

export default function ItemIcon({ name, size = 32 }: ItemIconProps) {
  const [error, setError] = useState(false);
  const src = `/assets/item/${name}.png`;

  if (error) {
    return (
      <div
        className="flex shrink-0 items-center justify-center rounded bg-tft-border text-xs font-bold text-gray-300"
        style={{ width: size, height: size }}
      >
        {name.charAt(0)}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={name}
      className="shrink-0 rounded object-cover"
      style={{ width: size, height: size }}
      onError={() => setError(true)}
    />
  );
}
