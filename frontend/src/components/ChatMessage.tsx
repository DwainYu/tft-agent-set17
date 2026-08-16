import { useState } from "react";
import clsx from "clsx";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMsg, SSEStage, CompCard as CompCardType } from "../types";
import CompCard from "./CompCard";
import ReasoningPanel from "./ReasoningPanel";

interface ChatMessageProps {
  message: ChatMsg;
}

/** Custom markdown components styled for the dark TFT theme. */
const mdComponents = {
  h1: ({ children }: { children?: React.ReactNode }) => (
    <h1 className="mb-2 mt-3 text-base font-bold text-tft-gold">{children}</h1>
  ),
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="mb-1.5 mt-3 text-sm font-bold text-tft-gold">{children}</h2>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="mb-1 mt-2 text-sm font-semibold text-gray-200">{children}</h3>
  ),
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="mb-2 text-sm leading-relaxed last:mb-0">{children}</p>
  ),
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="mb-2 list-disc space-y-0.5 pl-4 text-sm">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="mb-2 list-decimal space-y-0.5 pl-4 text-sm">{children}</ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="leading-relaxed">{children}</li>
  ),
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-white">{children}</strong>
  ),
  code: ({ children }: { children?: React.ReactNode }) => (
    <code className="rounded bg-tft-dark/60 px-1 py-0.5 font-mono text-xs text-tft-gold">
      {children}
    </code>
  ),
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="mb-2 overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: React.ReactNode }) => (
    <thead className="border-b border-tft-border">{children}</thead>
  ),
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="px-2 py-1 text-left text-xs font-semibold text-gray-400">
      {children}
    </th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => (
    <td className="border-b border-tft-border/40 px-2 py-1 text-gray-300">
      {children}
    </td>
  ),
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="mb-2 border-l-2 border-tft-gold/50 pl-3 text-sm text-gray-400">
      {children}
    </blockquote>
  ),
};

export default function ChatMessage({ message }: ChatMessageProps) {
  const [reasoningExpanded, setReasoningExpanded] = useState(false);
  const isUser = message.role === "user";

  return (
    <div
      className={clsx(
        "flex w-full animate-msg-in",
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
        {/* Text content — markdown for assistant, plain for user */}
        {message.content &&
          (isUser ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed">
              {message.content}
            </p>
          ) : (
            <div className="markdown-body">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={mdComponents as never}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          ))}

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
        {!isUser && message.card && "comp_name" in message.card && (
          <CompCard data={message.card as CompCardType} />
        )}

        {/* Results list (e.g. item search results) — skip when CompCard already shown */}
        {!isUser &&
          message.results &&
          message.results.length > 0 &&
          !(message.card && "comp_name" in message.card) && (
            <ul className="space-y-1">
              {message.results.map((r, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between rounded bg-tft-dark/40 px-3 py-1.5 text-sm"
                >
                  <span className="text-gray-200">
                    {(r.name_zh as string) ??
                      (r.name as string) ??
                      JSON.stringify(r)}
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
