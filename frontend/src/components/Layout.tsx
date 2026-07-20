import { useState } from "react";
import clsx from "clsx";
import { Menu, X } from "lucide-react";
import { AuthProvider } from "../context/AuthContext";
import { ConversationProvider } from "../context/ConversationContext";
import Sidebar from "./Sidebar";
import ChatArea from "./ChatArea";

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <AuthProvider>
      <ConversationProvider>
        <div className="relative flex h-screen overflow-hidden bg-tft-dark text-white">
          {/* Mobile sidebar overlay */}
          {sidebarOpen && (
            <div
              className="fixed inset-0 z-30 bg-black/50 md:hidden"
              onClick={() => setSidebarOpen(false)}
            />
          )}

          {/* Sidebar */}
          <aside
            className={clsx(
              "fixed inset-y-0 left-0 z-40 w-64 transform transition-transform duration-200 md:relative md:translate-x-0",
              sidebarOpen ? "translate-x-0" : "-translate-x-full"
            )}
          >
            <Sidebar />
          </aside>

          {/* Main area */}
          <main className="flex flex-1 flex-col overflow-hidden">
            {/* Mobile hamburger */}
            <div className="flex items-center border-b border-tft-border px-3 py-2 md:hidden">
              <button
                type="button"
                onClick={() => setSidebarOpen((v) => !v)}
                className="rounded p-1 text-gray-400 hover:text-white transition-colors"
              >
                {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
              </button>
              <span className="ml-2 text-sm font-semibold text-tft-gold">
                TFT Agent
              </span>
            </div>

            <div className="flex-1 overflow-hidden">
              <ChatArea />
            </div>
          </main>
        </div>
      </ConversationProvider>
    </AuthProvider>
  );
}
