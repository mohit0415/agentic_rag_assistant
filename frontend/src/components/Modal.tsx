import React, { useEffect } from "react";
import StringData from "../StringData";

export type ModalVariant = "success" | "error";

export interface ModalAction {
  label: string;
  onClick: () => void;
  kind?: "primary" | "ghost";
}

export interface ModalProps {
  open: boolean;
  variant?: ModalVariant;
  title: string;
  message: string;
  details?: string;
  actions?: ModalAction[];
  onClose: () => void;
}

const VARIANTS: Record<
  ModalVariant,
  { ring: string; iconBg: string; iconColor: string; icon: string; accent: string }
> = {
  success: {
    ring: "border-success/25",
    iconBg: "bg-success/10",
    iconColor: "text-[#4ADE80]",
    icon: "✓",
    accent: "#22C55E",
  },
  error: {
    ring: "border-danger/30",
    iconBg: "bg-danger/10",
    iconColor: "text-[#F87171]",
    icon: "✕",
    accent: "#EF4444",
  },
};

const Modal: React.FC<ModalProps> = ({
  open,
  variant = "success",
  title,
  message,
  details,
  actions,
  onClose,
}) => {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const v = VARIANTS[variant];
  const resolvedActions: ModalAction[] =
    actions && actions.length > 0
      ? actions
      : [{ label: StringData.modal.closeBtn, onClick: onClose, kind: "primary" }];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-[fadeIn_0.15s_ease-out]"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className={`w-full max-w-sm rounded-modal border ${v.ring} bg-card/90 shadow-modal backdrop-blur-xl p-6 flex flex-col items-center text-center animate-[popIn_0.18s_ease-out]`}
      >
        <button
          onClick={onClose}
          aria-label={StringData.modal.dismissAria}
          className="self-end -mt-2 -mr-2 flex h-7 w-7 items-center justify-center rounded-lg text-txt-mut hover:bg-white/[0.06] hover:text-txt-pri text-lg leading-none transition-colors"
        >
          ×
        </button>

        <div
          className={`w-14 h-14 rounded-full ${v.iconBg} ${v.iconColor} flex items-center justify-center text-2xl font-bold mb-4`}
        >
          {v.icon}
        </div>

        <h2 className="text-[15px] font-semibold text-txt-pri mb-1.5">{title}</h2>
        <p className="text-[12.5px] text-txt-sec leading-relaxed">{message}</p>

        {details && (
          <p className="mt-2 w-full rounded-xl bg-ink/60 border border-line px-3 py-2 text-[11px] text-txt-mut break-words">
            {details}
          </p>
        )}

        <div className="flex flex-col-reverse sm:flex-row gap-2 w-full mt-5">
          {resolvedActions.map((action, i) => {
            const primary = (action.kind ?? "primary") === "primary";
            return (
              <button
                key={`${action.label}-${i}`}
                onClick={action.onClick}
                className={
                  primary
                    ? "flex-1 rounded-xl px-4 py-2 text-[12.5px] font-semibold text-[#04121A] transition-all duration-150 hover:brightness-110 active:scale-95"
                    : "flex-1 rounded-xl px-4 py-2 text-[12.5px] font-medium text-txt-sec border border-line bg-white/[0.03] hover:text-txt-pri hover:border-line-strong transition-colors"
                }
                style={primary ? { backgroundColor: v.accent } : undefined}
              >
                {action.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default Modal;
