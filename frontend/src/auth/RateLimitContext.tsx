import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { RATE_LIMITED_EVENT, regenerateSessionId } from "./token";
export { formatCountdown } from "../utils/time";

interface RateLimitContextValue {
  limited: boolean;
  remaining: number;
}

const RateLimitContext = createContext<RateLimitContextValue>({
  limited: false,
  remaining: 0,
});

export const RateLimitProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [remaining, setRemaining] = useState(0);
  const intervalRef = useRef<number | null>(null);

  const stopTimer = useCallback(() => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const startCooldown = useCallback(
    (seconds: number) => {
      stopTimer();
      setRemaining(seconds);
      intervalRef.current = window.setInterval(() => {
        setRemaining((prev) => {
          if (prev <= 1) {
            stopTimer();
            regenerateSessionId();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    },
    [stopTimer],
  );

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ retryAfter?: number }>).detail;
      const seconds = Math.max(1, Math.ceil(detail?.retryAfter ?? 60));
      setRemaining((prev) => {
        if (seconds > prev) {
          startCooldown(seconds);
          return seconds;
        }
        return prev;
      });
    };
    window.addEventListener(RATE_LIMITED_EVENT, handler);
    return () => {
      window.removeEventListener(RATE_LIMITED_EVENT, handler);
      stopTimer();
    };
  }, [startCooldown, stopTimer]);

  const value = useMemo<RateLimitContextValue>(
    () => ({ limited: remaining > 0, remaining }),
    [remaining],
  );

  return (
    <RateLimitContext.Provider value={value}>{children}</RateLimitContext.Provider>
  );
};

export function useRateLimit(): RateLimitContextValue {
  return useContext(RateLimitContext);
}

export default RateLimitContext;
