import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import URLS from "../config/urls";
import { ApiError } from "../utils/network";
import {
  UNAUTHORIZED_EVENT,
  clearSessionId,
  clearToken,
  decodeJwt,
  ensureSessionId,
  getToken,
  isTokenExpired,
  regenerateSessionId,
  setToken,
} from "./token";

export interface ModelInfo {
  provider: string;
  llmModel: string | null;
  embedModel: string | null;
}

export interface LoginExtras {
  llamaparseApiKey?: string;
}

interface AuthContextValue {
  isAuthenticated: boolean;
  username: string | null;
  models: ModelInfo | null;
  login: (username: string, password: string, extras?: LoginExtras) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function readSession(): { token: string | null; username: string | null } {
  const token = getToken();
  if (!token || isTokenExpired(token)) {
    if (token) clearToken();
    return { token: null, username: null };
  }
  ensureSessionId();
  return { token, username: decodeJwt(token)?.sub ?? null };
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [session, setSession] = useState(readSession);
  const [models, setModels] = useState<ModelInfo | null>(null);

  const logout = useCallback(() => {
    clearToken();
    clearSessionId();
    setModels(null);
    setSession({ token: null, username: null });
  }, []);

  const login = useCallback(
    async (username: string, password: string, extras?: LoginExtras) => {
      let res: Response;
      try {
        res = await fetch(URLS.login, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username,
            password,
            llamaparse_api_key: extras?.llamaparseApiKey?.trim() || undefined,
          }),
        });
      } catch (e) {
        const original = e instanceof Error ? `${e.name}: ${e.message}` : String(e);
        throw new ApiError(
          `Network error — is the server running? (${original})`,
          0,
          original,
        );
      }

      if (!res.ok) {
        let detail = "Incorrect username or password.";
        try {
          const data = await res.json();
          if (typeof data?.detail === "string") detail = data.detail;
        } catch {
        }
        throw new ApiError(detail, res.status);
      }

      const data = await res.json();
      const token: string = data.access_token;
      setToken(token);
      regenerateSessionId();
      if (data?.provider) {
        setModels({
          provider: data.provider,
          llmModel: data.llm_model ?? null,
          embedModel: data.embed_model ?? null,
        });
      }
      setSession({ token, username: decodeJwt(token)?.sub ?? username });
    },
    [],
  );

  useEffect(() => {
    const handler = () => logout();
    window.addEventListener(UNAUTHORIZED_EVENT, handler);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handler);
  }, [logout]);

  useEffect(() => {
    if (!session.token) return;
    const payload = decodeJwt(session.token);
    if (!payload?.exp) return;
    const msLeft = payload.exp * 1000 - Date.now();
    if (msLeft <= 0) {
      logout();
      return;
    }
    const timer = window.setTimeout(logout, msLeft);
    return () => window.clearTimeout(timer);
  }, [session.token, logout]);

  useEffect(() => {
    if (!session.token || models) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(URLS.models, {
          headers: { Authorization: `Bearer ${session.token}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && data?.provider) {
          setModels({
            provider: data.provider,
            llmModel: data.llm_model ?? null,
            embedModel: data.embed_model ?? null,
          });
        }
      } catch {
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [session.token, models]);

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: !!session.token,
      username: session.username,
      models,
      login,
      logout,
    }),
    [session, models, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

export default AuthContext;
