import React, { useEffect, useRef, useState } from "react";
import StringData from "../StringData";

export interface EvalScores {
  faithfulness: number | null;
  relevance: number | null;
}

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

const ANIM_MS = 1200;

function useCountUp(target: number | null): number | null {
  const [value, setValue] = useState<number | null>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    cancelAnimationFrame(rafRef.current);
    if (target === null) {
      setValue(null);
      return;
    }
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ANIM_MS);
      setValue(target * easeOut(t));
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target]);

  return value;
}

function scoreColor(v: number | null): string {
  if (v === null) return "#7B8794";
  if (v < 0.5) return "#EF4444";
  if (v < 0.75) return "#F59E0B";
  return "#22C55E";
}

const RING_SIZE = 74;
const STROKE = 5;
const RADIUS = (RING_SIZE - STROKE) / 2;
const CIRCUM = 2 * Math.PI * RADIUS;

interface ScoreRingProps {
  label: string;
  target: number | null;
}

const ScoreRing: React.FC<ScoreRingProps> = ({ label, target }) => {
  const value = useCountUp(target);
  const clamped = value === null ? 0 : Math.max(0, Math.min(1, value));
  const color = scoreColor(value);

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: RING_SIZE, height: RING_SIZE }}>
        <svg width={RING_SIZE} height={RING_SIZE} className="-rotate-90">
          <circle
            cx={RING_SIZE / 2}
            cy={RING_SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke="rgba(255,255,255,0.07)"
            strokeWidth={STROKE}
          />
          <circle
            cx={RING_SIZE / 2}
            cy={RING_SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke={color}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={CIRCUM}
            strokeDashoffset={CIRCUM * (1 - clamped)}
          />
        </svg>
        <span
          className="absolute inset-0 flex items-center justify-center text-sm font-semibold tabular-nums"
          style={{ color: value === null ? "#7B8794" : "#F8FAFC" }}
        >
          {value === null ? StringData.nav.evalEmpty : clamped.toFixed(2)}
        </span>
      </div>
      <span className="text-[10px] font-medium text-txt-mut">{label}</span>
    </div>
  );
};

interface EvalScorePanelProps {
  scores: EvalScores;
  isThinking?: boolean;
}

const EvalScorePanel: React.FC<EvalScorePanelProps> = ({ scores, isThinking = false }) => {
  const noScores = scores.faithfulness === null && scores.relevance === null;

  return (
    <div className="border-t border-line bg-ink/30 px-3 py-3.5">
      <p className="ml-label flex items-center gap-1.5 pb-2.5">
        {StringData.nav.evalSectionLabel}
        {isThinking && (
          <span className="h-2 w-2 animate-spin rounded-full border border-accent border-t-transparent" />
        )}
      </p>
      <div className="flex justify-around">
        <ScoreRing label={StringData.nav.evalFaithfulness} target={scores.faithfulness} />
        <ScoreRing label={StringData.nav.evalRelevance} target={scores.relevance} />
      </div>
      {noScores && !isThinking && (
        <p className="pt-2.5 text-center text-[10px] text-txt-mut">
          {StringData.nav.evalPendingHint}
        </p>
      )}
    </div>
  );
};

export default EvalScorePanel;
