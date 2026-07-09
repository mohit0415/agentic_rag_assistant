
export function formatCountdown(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;

  const pad = (n: number) => String(n).padStart(2, "0");

  // Daily rate limits can produce multi-hour cooldowns; show days/hours cleanly.
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}:${pad(m)}:${pad(sec)}`;
  if (m > 0) return `${m}:${pad(sec)}`;
  return `${sec}s`;
}
