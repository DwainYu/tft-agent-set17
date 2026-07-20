import { useEffect, useRef, useState } from "react";
import { Send, Loader2 } from "lucide-react";
import type { ChatMsg, Direction, SSEStage } from "../types";
import { useSSE } from "../hooks/useSSE";
import ChatMessage from "./ChatMessage";
import DirectionTabs from "./DirectionTabs";
import ReasoningPanel from "./ReasoningPanel";

let nextId = 0;
function uid() {
  return `msg-${Date.now()}-${nextId++}`;
}

export default function ChatArea() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [direction, setDirection] = useState<Direction | undefined>(undefined);
  const [reasoningExpanded, setReasoningExpanded] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { ask, stage, reasoning, loading, card, results, summary } = useSSE();

  // Auto-scroll on new messages or streaming updates
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, stage]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMsg = {
      id: uid(),
      role: "user",
      content: text,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    try {
      const result = await ask(text, direction);

      const assistantMsg: ChatMsg = {
        id: uid(),
        role: "assistant",
        content: result.summary,
        card: result.card,
        results: result.results,
        reasoning: result.reasoning,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errMsg: ChatMsg = {
        id: uid(),
        role: "assistant",
        content: `请求失败：${err instanceof Error ? err.message : "未知错误"}`,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errMsg]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Message list */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-gray-500">
            <p className="text-center text-sm">
              选择下方模式，输入你的问题开始对话
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
      </div>

      {/* Live reasoning panel while loading */}
      {loading && stage && (
        <div className="px-4 pb-2">
          <ReasoningPanel
            stage={stage as SSEStage | null}
            reasoning={reasoning ?? {}}
            expanded={reasoningExpanded}
            onToggle={() => setReasoningExpanded((v) => !v)}
          />
        </div>
      )}

      {/* Direction tabs */}
      <DirectionTabs value={direction} onChange={setDirection} />

      {/* Input area */}
      <div className="flex items-end gap-2 border-t border-tft-border bg-tft-card px-4 py-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，例如：推荐一套当前版本强势阵容"
          rows={1}
          className="max-h-32 flex-1 resize-none rounded-lg border border-tft-border bg-tft-dark px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-tft-gold transition-colors"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-tft-gold text-tft-dark transition-colors hover:bg-tft-goldDark disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
        </button>
      </div>
    </div>
  );
}
