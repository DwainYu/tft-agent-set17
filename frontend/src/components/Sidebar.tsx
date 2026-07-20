import { useState } from "react";
import clsx from "clsx";
import { MessageSquare, Plus, LogOut, Menu, X } from "lucide-react";
import { useAuthContext } from "../context/AuthContext";
import { useConversationContext } from "../context/ConversationContext";

export default function Sidebar() {
  const { user, login, logout } = useAuthContext();
  const {
    conversations,
    selectedId,
    selectConversation,
    createConversation,
  } = useConversationContext();

  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");

  const handleLogin = async () => {
    setLoginError("");
    try {
      await login(phone, password);
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "登录失败");
    }
  };

  return (
    <div className="flex h-full flex-col border-r border-tft-border bg-tft-card">
      {/* App title */}
      <div className="flex items-center gap-2 px-4 py-4">
        <MessageSquare size={20} className="text-tft-gold" />
        <h1 className="text-lg font-bold text-tft-gold">TFT Agent</h1>
      </div>

      {/* New chat button */}
      <div className="px-3">
        <button
          type="button"
          onClick={() => createConversation()}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-tft-border px-3 py-2 text-sm text-gray-300 transition-colors hover:border-tft-gold hover:text-tft-gold"
        >
          <Plus size={16} />
          新对话
        </button>
      </div>

      {/* Conversation list */}
      <div className="mt-3 flex-1 space-y-0.5 overflow-y-auto px-2">
        {conversations.map((conv) => (
          <button
            key={conv.id}
            type="button"
            onClick={() => selectConversation(conv.id)}
            className={clsx(
              "flex w-full items-center gap-2 truncate rounded-lg px-3 py-2 text-left text-sm transition-colors",
              selectedId === conv.id
                ? "bg-tft-dark text-white"
                : "text-gray-400 hover:bg-tft-dark/50 hover:text-gray-200"
            )}
          >
            <MessageSquare size={14} className="shrink-0" />
            <span className="truncate">
              {conv.title ?? `对话 ${conv.id.toString().slice(0, 6)}`}
            </span>
          </button>
        ))}
      </div>

      {/* Bottom — auth section */}
      <div className="border-t border-tft-border px-3 py-3">
        {user ? (
          <div className="flex items-center justify-between">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-gray-300">{user.phone}</p>
              <p className="text-xs text-gray-500">已登录</p>
            </div>
            <button
              type="button"
              onClick={logout}
              className="ml-2 flex shrink-0 items-center gap-1 rounded px-2 py-1 text-xs text-gray-400 transition-colors hover:text-red-400"
            >
              <LogOut size={14} />
              退出
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="手机号"
              className="w-full rounded-lg border border-tft-border bg-tft-dark px-3 py-1.5 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-tft-gold"
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="密码"
              className="w-full rounded-lg border border-tft-border bg-tft-dark px-3 py-1.5 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-tft-gold"
            />
            {loginError && (
              <p className="text-xs text-red-400">{loginError}</p>
            )}
            <button
              type="button"
              onClick={handleLogin}
              className="w-full rounded-lg bg-tft-gold px-3 py-1.5 text-sm font-semibold text-tft-dark transition-colors hover:bg-tft-goldDark"
            >
              登录
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
