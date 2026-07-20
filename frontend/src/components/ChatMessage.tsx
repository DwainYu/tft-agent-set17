import { useState } from "react";
import clsx from "clsx";
import type { ChatMsg, SSEStage } from "../types";
import CompCard from "./CompCard";
import ReasoningPanel from "./ReasoningPanel";

interface ChatMessageProps {
  message: ChatMsg;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const [reasoningExpanded, setReasoningExpanded] = useState(false);
  const isUser = message.role === "user";

  return (
    <div
      className={clsx(
        "flex w-full",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={clsx(
          "max-w-[85%] space-y-2 rounded-2xl px-4 py-2.5",
          isUser
            ? "bg-tft-blue text-white"
            : "border border-tft-border bg-tft-card text-gray-100"
        )}
      >
        {/* Text content */}
        {message.content && (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">
            {message.content}
          </p>
        )}

        {/* Reasoning panel (assistant only) */}
        {!isUser && message.reasoning && (
          <ReasoningPanel
            stage={null}
            reasoning={message.reasoning as Partial<Record<SSEStage, string>>}
            expanded={reasoningExpanded}
            onToggle={() => setReasoningExpanded((v) => !v)}
          />
        )}

        {/* Composition card (only if it has CompCard structure) */}
        {!isUser && message.card && 'comp_name' in message.card && (
          <CompCard data={message.card} />
        )}

        {/* Results list (e.g. item search results) — skip when CompCard already shown */}
        {!isUser && message.results && message.results.length > 0 && !(message.card && 'comp_name' in message.card) && (
          <ul className="space-y-1">
            {message.results.map((r, i) => (
              <li
                key={i}
                className="flex items-center justify-between rounded bg-tft-dark/40 px-3 py-1.5 text-sm"
              >
                <span className="text-gray-200">
                  {(r.name_zh as string) ?? (r.name as string) ?? JSON.stringify(r)}
                </span>
                {typeof r.delta === "number" && (
                  <span
                    className={clsx(
                      "ml-2 font-mono text-xs",
                      r.delta < 0 ? "text-green-400" : "text-red-400"
                    )}
                  >
                    {(r.delta as number) > 0 ? "+" : ""}
                    {r.delta as number}
                  </span>
                )}
                {typeof r.delta_rank === "number" && (
                  <span
                    className={clsx(
                      "ml-2 font-mono text-xs",
                      r.delta_rank < 0 ? "text-green-400" : "text-red-400"
                    )}
                  >
                    {(r.delta_rank as number) > 0 ? "+" : ""}
                    {r.delta_rank as number}
                  </span>
                )}
                {typeof r.sample_size === "number" && (
                  <span className="ml-2 text-xs text-gray-500">
                    n={r.sample_size as number}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
