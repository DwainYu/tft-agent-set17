import clsx from "clsx";
import { Check, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import type { SSEStage } from "../types";
import { STAGE_ORDER, STAGE_LABELS } from "../hooks/useSSE";

interface ReasoningPanelProps {
  stage: SSEStage | null;
  reasoning: Partial<Record<SSEStage, string>>;
  expanded: boolean;
  onToggle: () => void;
}

function StageStatus({ stage, currentStage }: { stage: SSEStage; currentStage: SSEStage | null }) {
  const currentIdx = currentStage ? STAGE_ORDER.indexOf(currentStage) : -1;
  const stageIdx = STAGE_ORDER.indexOf(stage);

  if (currentIdx < 0 || stageIdx < currentIdx) {
    // completed
    return <Check size={16} className="shrink-0 text-green-400" />;
  }

  if (stageIdx === currentIdx) {
    // current — pulsing dot
    return (
      <span className="relative flex h-4 w-4 shrink-0 items-center justify-center">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-tft-gold opacity-75" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-tft-gold" />
      </span>
    );
  }

  // pending
  return <span className="inline-block h-4 w-4 shrink-0 rounded-full border-2 border-gray-600" />;
}

export default function ReasoningPanel({
  stage,
  reasoning,
  expanded,
  onToggle,
}: ReasoningPanelProps) {
  return (
    <div className="rounded-lg border border-tft-border bg-tft-card/60 text-sm">
      {/* Header — click to toggle */}
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-2 px-3 py-2 text-gray-300 hover:text-white transition-colors"
      >
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <Loader2 size={14} className={clsx("text-tft-gold", stage && "animate-spin")} />
        <span className="font-medium">推理过程</span>
      </button>

      {/* Body */}
      {expanded && (
        <ul className="space-y-1 px-3 pb-3">
          {STAGE_ORDER.map((s) => {
            const currentIdx = stage ? STAGE_ORDER.indexOf(stage) : -1;
            const stageIdx = STAGE_ORDER.indexOf(s);
            const isDone = currentIdx >= 0 && stageIdx < currentIdx;
            const isCurrent = stageIdx === currentIdx;

            return (
              <li key={s} className="flex items-start gap-2">
                <StageStatus stage={s} currentStage={stage} />
                <div className="min-w-0 flex-1">
                  <span
                    className={clsx(
                      "text-xs",
                      isDone && "text-green-400",
                      isCurrent && "text-tft-gold",
                      !isDone && !isCurrent && "text-gray-500"
                    )}
                  >
                    {STAGE_LABELS[s]}
                  </span>
                  {reasoning[s] && (
                    <p className="mt-0.5 text-xs text-gray-400 break-words">
                      {reasoning[s]}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
