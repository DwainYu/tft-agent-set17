interface TraitBadgeProps {
  name: string;
}

export default function TraitBadge({ name }: TraitBadgeProps) {
  return (
    <span className="inline-block rounded-full border border-tft-border bg-tft-dark/60 px-2.5 py-0.5 text-sm text-gray-300">
      {name}
    </span>
  );
}
