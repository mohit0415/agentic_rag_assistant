import React from "react";
import { useNavigate } from "react-router-dom";
import { Cpu, LogOut, Menu, PanelRight } from "lucide-react";
import StringData from "../StringData";
import { useAuth } from "../auth/AuthContext";

interface TopBarProps {
  title?: string;
  subtitle?: string;
  modelName?: string;
  onToggleLeft?: () => void;
  onToggleRight?: () => void;
}

const TopBar: React.FC<TopBarProps> = ({
  title = StringData.chat.title,
  subtitle = StringData.chat.titleSuffix,
  modelName,
  onToggleLeft,
  onToggleRight,
}) => {
  const { username, logout, models } = useAuth();
  const navigate = useNavigate();

  const activeModel =
    modelName || models?.embedModel || StringData.chat.modelBadge;
  const modelTooltip = models
    ? `Provider: ${models.provider}\nLLM: ${models.llmModel ?? "—"}\nEmbeddings: ${models.embedModel ?? "—"}`
    : undefined;

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="flex items-center justify-between gap-2 border-b border-line bg-surface/40 px-4 py-3 backdrop-blur-xl">
      <div className="flex min-w-0 items-center gap-2">
        {onToggleLeft && (
          <button
            onClick={onToggleLeft}
            aria-label="Open documents panel"
            className="-ml-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg text-txt-mut transition-colors hover:bg-white/[0.06] hover:text-accent lg:hidden"
          >
            <Menu size={16} />
          </button>
        )}
        <p className="truncate text-sm font-medium text-txt-mut">
          <strong className="font-semibold text-txt-pri">{title}</strong>
          <span className="hidden sm:inline">{subtitle ? ` · ${subtitle}` : ""}</span>
        </p>
      </div>
      <div className="flex flex-shrink-0 items-center gap-2">
        <div
          title={modelTooltip}
          className="hidden items-center gap-1.5 rounded-full border border-accent/20 bg-accent/[0.06] px-3 py-1 text-[11px] font-medium text-accent sm:flex"
        >
          <Cpu size={11} />
          <span className="max-w-[180px] truncate">{activeModel}</span>
        </div>

        {username && (
          <div className="hidden items-center gap-2 md:flex">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-[#22D3EE]/80 to-[#3B82F6]/80 text-[10px] font-semibold uppercase text-[#04121A]">
              {username.slice(0, 2)}
            </div>
            <span className="text-[11.5px] font-medium text-txt-sec">{username}</span>
          </div>
        )}

        <button
          onClick={handleLogout}
          aria-label="Log out"
          title="Log out"
          className="flex items-center gap-1.5 rounded-lg border border-line bg-white/[0.03] px-2.5 py-1.5 text-[11px] font-medium text-txt-mut transition-all duration-200 hover:border-danger/40 hover:bg-danger/[0.06] hover:text-[#FCA5A5]"
        >
          <LogOut size={12} aria-hidden="true" />
          <span className="hidden sm:inline">Logout</span>
        </button>

        {onToggleRight && (
          <button
            onClick={onToggleRight}
            aria-label="Open sources and pipeline panel"
            className="-mr-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg text-txt-mut transition-colors hover:bg-white/[0.06] hover:text-accent lg:hidden"
          >
            <PanelRight size={16} />
          </button>
        )}
      </div>
    </div>
  );
};

export default TopBar;
