import React, { useRef, useEffect } from "react";
import { HeartPulse, Table2, User, Wrench } from "lucide-react";
import StringData from "../StringData";
import Markdown from "./Markdown";
import type { Message, Citation, SourceChip } from "../hooks/useChat";

export type { Message, Citation, SourceChip };

interface ChatAreaProps {
  messages: Message[];
  isThinking: boolean;
  thinkingLabel?: string;
  onCitationClick: (chunkIndex: number) => void;
  onSourceChipClick: (chunkIndex: number) => void;
}

const TypingIndicator: React.FC<{ label: string }> = ({ label }) => (
  <div className="flex animate-fade-in gap-3">
    <Avatar role="ai" />
    <div className="flex items-center gap-2.5 rounded-2xl border border-line bg-card/60 px-4 py-2.5 text-[12px] text-txt-mut">
      <div className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent"
            style={{ animationDelay: `${i * 0.18}s` }}
          />
        ))}
      </div>
      <span>{label}</span>
    </div>
  </div>
);

const Avatar: React.FC<{ role: "ai" | "user" }> = ({ role }) => (
  <div
    className={`flex h-[32px] w-[32px] flex-shrink-0 items-center justify-center rounded-xl ${
      role === "ai"
        ? "bg-gradient-to-br from-[#22D3EE] to-[#3B82F6] text-[#04121A] shadow-glow-soft"
        : "border border-line bg-card text-txt-sec"
    }`}
  >
    {role === "ai" ? <HeartPulse size={15} strokeWidth={2.2} /> : <User size={14} />}
  </div>
);

const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  isThinking,
  thinkingLabel,
  onCitationClick,
  onSourceChipClick,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  const last = messages[messages.length - 1];
  const showTyping =
    isThinking && (!last || last.role !== "ai" || (last.streaming && last.content === ""));

  return (
    <div
      className="flex flex-1 flex-col gap-4 overflow-y-auto p-4 sm:p-5"
      aria-label={StringData.aria.chatArea}
    >
      {messages.map((msg) => {
        if (msg.role === "ai" && msg.streaming && msg.content === "") return null;

        return (
          <div
            key={msg.id}
            className={`flex max-w-full animate-rise-in gap-3 ${
              msg.role === "user" ? "flex-row-reverse" : ""
            }`}
          >
            <Avatar role={msg.role} />
            <div
              className={`max-w-[78%] rounded-2xl px-4 py-3 text-[13px] leading-relaxed transition-colors ${
                msg.error
                  ? "border border-danger/30 bg-danger/[0.08] text-[#FECACA]"
                  : msg.role === "ai"
                  ? "border border-line bg-card/70 text-txt-sec shadow-card backdrop-blur-sm"
                  : "border border-accent/25 bg-gradient-to-br from-accent/[0.08] to-accent-2/[0.08] text-txt-pri"
              }`}
            >
              {msg.role === "ai" && !msg.error ? (
                <div className="markdown-content">
                  <Markdown>{msg.content}</Markdown>
                  {msg.streaming && <span className="stream-caret" />}
                </div>
              ) : (
                <p className="whitespace-pre-wrap">
                  {msg.content}
                  {msg.streaming && <span className="stream-caret" />}
                </p>
              )}

              {msg.tables && msg.tables.length > 0 && (
                <div className="mt-3 flex flex-col gap-2.5">
                  {msg.tables.map((t) => (
                    <div
                      key={`table-${t.index}`}
                      className="rounded-xl border border-line bg-ink/50 p-3"
                    >
                      <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-medium text-txt-mut">
                        <Table2 size={11} className="text-accent" />
                        <span>Table</span>
                        {t.source && <span className="truncate">· {t.source}</span>}
                        <span className="text-txt-mut/60">[{t.index}]</span>
                      </div>
                      <Markdown>{t.markdown}</Markdown>
                    </div>
                  ))}
                </div>
              )}

              {msg.images && msg.images.length > 0 && (
                <div className="mt-3 flex flex-col gap-2.5">
                  {msg.images.map((img) => (
                    <figure
                      key={`image-${img.index}-${img.url}`}
                      className="rounded-xl border border-line bg-ink/50 p-3"
                    >
                      <a href={img.url} target="_blank" rel="noopener noreferrer">
                        <img
                          src={img.url}
                          alt={img.caption ?? "Retrieved figure"}
                          loading="lazy"
                          className="max-w-full rounded-lg border border-line transition-transform duration-200 hover:scale-[1.01]"
                        />
                      </a>
                      {img.caption && (
                        <figcaption className="mt-1.5 text-[10.5px] leading-snug text-txt-mut">
                          {img.caption}
                          {img.source && (
                            <span className="text-txt-mut/60"> · {img.source}</span>
                          )}
                        </figcaption>
                      )}
                    </figure>
                  ))}
                </div>
              )}

              {msg.toolsUsed && msg.toolsUsed.length > 0 && (
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {msg.toolsUsed.map((tool) => (
                    <span
                      key={tool}
                      className="inline-flex items-center gap-1.5 rounded-md border border-success/20 bg-success/[0.07] px-2 py-0.5 text-[10px] font-medium text-[#4ADE80]"
                    >
                      <Wrench size={9} /> {tool}
                    </span>
                  ))}
                </div>
              )}

              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {msg.citations.map((c) => (
                    <button
                      key={c.chunkIndex}
                      onClick={() => onCitationClick(c.chunkIndex)}
                      className="inline-block cursor-pointer rounded-md border border-accent/30 bg-accent/[0.07] px-2 py-0.5 text-[10px] font-semibold text-accent transition-all duration-150 hover:bg-accent/[0.16] hover:shadow-glow-soft"
                    >
                      [{c.label}]
                    </button>
                  ))}
                </div>
              )}

              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5 border-t border-line pt-2.5">
                  {msg.sources.map((s) => (
                    <button
                      key={s.chunkIndex}
                      onClick={() => onSourceChipClick(s.chunkIndex)}
                      className="flex items-center gap-1.5 rounded-lg border border-line bg-ink/60 px-2.5 py-1 text-[10px] font-medium text-txt-mut transition-all duration-150 hover:border-accent/40 hover:text-accent"
                    >
                      <span>{s.icon}</span>
                      <span>{s.label}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}

      {showTyping && (
        <TypingIndicator
          label={
            thinkingLabel || StringData.chat.thinkingLabel.replace("{count}", "5")
          }
        />
      )}
      <div ref={bottomRef} />
    </div>
  );
};

export default ChatArea;
