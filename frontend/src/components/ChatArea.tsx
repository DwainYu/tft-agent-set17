import { useEffect, useRef, useState, useCallback } from "react";
import { Send, Loader2, Sparkles } from "lucide-react";
import type { ChatMsg, Direction, SSEStage } from "../types";
import { useSSE } from "../hooks/useSSE";
import { useAuthContext } from "../context/AuthContext";
import { useConversationContext } from "../context/ConversationContext";
import { conversationApi } from "../api/client";
import ChatMessage from "./ChatMessage";
import DirectionTabs from "./DirectionTabs";
import ReasoningPanel from "./ReasoningPanel";

let nextId = 0;
function uid() {
  return `msg-${Date.now()}-${nextId++}`;
}

/** Preset quick-start questions shown in the empty state. */
const QUICK_QUESTIONS: { label: string; question: string; direction?: Direction }[] = [
  { label: "当前版本强势阵容", question: "推荐一套当前版本强势阵容", direction: "推荐阵容" },
  { label: "锐雯主C怎么搭", question: "锐雯主C阵容怎么搭", direction: "推荐阵容" },
  { label: "劫出什么装备", question: "劫应该出什么装备", direction: "推荐装备" },
  { label: "游侠羁绊英雄", question: "游侠羁绊有哪些英雄", direction: "查专属" },
];

export default function ChatArea() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [direction, setDirection] = useState<Direction | undefined>(undefined);
  const [reasoningExpanded, setReasoningExpanded] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { user } = useAuthContext();
  const { selectedId, createConversation, selectConversation, refresh } =
    useConversationContext();

  const { ask, stage, reasoning, loading, card, results, summary } = useSSE();

  // Keep a ref to the latest selectedId for use inside async handlers
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;

  // Auto-scroll on new messages or streaming updates
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, stage]);

  // Load historical messages when switching conversations
  useEffect(() => {
    if (selectedId == null) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    setHistoryLoading(true);
    conversationApi
      .getMessages(selectedId)
      .then((res) => {
        if (cancelled) return;
        const loaded: ChatMsg[] = res.data.map((m) => ({
          id: `hist-${m.id}`,
          role: m.role as "user" | "assistant",
          content: m.content,
          timestamp: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
        }));
        setMessages(loaded);
      })
      .catch(() => {
        if (!cancelled) setMessages([]);
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  /** Persist a message to the backend (fire-and-forget). */
  const saveMessage = useCallback(
    (convId: number, role: string, content: string) => {
      conversationApi.addMessage(convId, role, content).catch(() => {
        // silent — persistence is best-effort
      });
    },
    [],
  );

  const handleSend = async (overrideQuestion?: string, overrideDirection?: Direction) => {
    const text = (overrideQuestion ?? input).trim();
    if (!text || loading) return;

    const dir = overrideDirection ?? direction;

    const userMsg: ChatMsg = {
      id: uid(),
      role: "user",
      content: text,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    if (overrideDirection) setDirection(overrideDirection);

    // Ensure we have a conversation (auto-create when logged in)
    let convId = selectedIdRef.current;
    if (user && convId == null) {
      try {
        const title = text.length > 20 ? text.slice(0, 20) + "…" : text;
        const conv = await conversationApi.create(title);
        convId = conv.data.id;
        selectConversation(conv.data.id);
        refresh();
      } catch {
        // proceed without persistence
      }
    }

    // Persist user message
    if (convId != null) {
      saveMessage(convId, "user", text);
    }

    try {
      const result = await ask(text, dir, convId != null ? String(convId) : undefined);

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

      // Persist assistant message
      if (convId != null) {
        saveMessage(convId, "assistant", result.summary);
      }
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
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4 scrollbar-thin">
        {historyLoading && (
          <div className="flex items-center justify-center py-8 text-gray-500">
            <Loader2 size={20} className="mr-2 animate-spin" />
            <span className="text-sm">加载历史消息…</span>
          </div>
        )}

        {!historyLoading && messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-6">
            <div className="text-center">
              <Sparkles size={32} className="mx-auto mb-3 text-tft-gold/60" />
              <p className="text-sm text-gray-400">
                选择下方模式，输入你的问题开始对话
              </p>
            </div>
            {/* Quick question chips */}
            <div className="flex max-w-md flex-wrap justify-center gap-2">
              {QUICK_QUESTIONS.map((q) => (
                <button
                  key={q.label}
                  type="button"
                  onClick={() => handleSend(q.question, q.direction)}
                  className="rounded-full border border-tft-border bg-tft-card px-4 py-2 text-sm text-gray-300 transition-colors hover:border-tft-gold hover:text-tft-gold"
                >
                  {q.label}
                </button>
              ))}
            </div>
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
          onClick={() => handleSend()}
          disabled={loading || !input.trim()}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-tft-gold text-tft-dark transition-colors hover:bg-tft-goldDark disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
        </button>
      </div>
    </div>
  );
}
