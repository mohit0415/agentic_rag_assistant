import React, { useState, useRef, useLayoutEffect } from "react";
import { Clock, FileText, Send } from "lucide-react";
import StringData from "../StringData";
import { useRateLimit, formatCountdown } from "../auth/RateLimitContext";

interface ChatInputProps {
  docCount: number;
  onSend: (text: string) => void;
  disabled?: boolean;
}

const MAX_TEXTAREA_HEIGHT = 160;

const ChatInput: React.FC<ChatInputProps> = ({ docCount, onSend, disabled }) => {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { limited, remaining } = useRateLimit();

  const isLocked = disabled || limited;

  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
    el.style.overflowY = el.scrollHeight > MAX_TEXTAREA_HEIGHT ? "auto" : "hidden";
  }, [value]);

  const handleSend = () => {
    const text = value.trim();
    if (!text || isLocked) return;
    onSend(text);
    setValue("");
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-line bg-surface/40 px-4 py-3.5 backdrop-blur-xl">
      {limited && (
        <div className="mb-2.5 flex animate-fade-in items-center gap-2 rounded-xl border border-warning/30 bg-warning/[0.08] px-3.5 py-2.5 text-[12px] text-[#FDE68A]">
          <Clock size={13} aria-hidden="true" className="flex-shrink-0 text-warning" />
          <span>
            Rate limit reached. Come back in{" "}
            <strong className="tabular-nums text-warning">
              {formatCountdown(remaining)}
            </strong>
            .
          </span>
        </div>
      )}

      <div className="flex items-end gap-2.5">
        <div
          className={`flex flex-1 items-start gap-2.5 rounded-2xl border bg-card/70 px-3.5 py-2.5 backdrop-blur transition-all duration-200 ${
            limited
              ? "border-warning/30"
              : "border-line focus-within:border-accent/45 focus-within:shadow-glow-cyan"
          }`}
        >
          <span className="mt-0.5 inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-line bg-ink/60 px-2 py-0.5 text-[10px] font-medium text-txt-mut">
            <FileText size={9} className="text-accent/80" />
            {StringData.chat.scopeBadge.replace("{count}", String(docCount))}
          </span>
          <textarea
            ref={inputRef}
            rows={1}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              limited
                ? `Paused — come back in ${formatCountdown(remaining)}…`
                : StringData.chat.inputPlaceholder
            }
            disabled={isLocked}
            className="block flex-1 resize-none border-none bg-transparent font-sans text-[13px] leading-5 text-txt-pri outline-none placeholder:text-txt-mut disabled:cursor-not-allowed disabled:opacity-60"
          />
        </div>
        <button
          onClick={handleSend}
          disabled={isLocked || !value.trim()}
          aria-label={StringData.aria.sendButton}
          className="btn-primary h-[42px] w-[42px] flex-shrink-0 !rounded-xl !p-0"
        >
          {limited ? <Clock size={16} /> : <Send size={16} />}
        </button>
      </div>
    </div>
  );
};

export default ChatInput;
