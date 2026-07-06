
const TOKEN_KEY = "docmind_token";
const SESSION_KEY = "docmind_session_id";

export const UNAUTHORIZED_EVENT = "auth:unauthorized";

export const RATE_LIMITED_EVENT = "api:rate-limited";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
  }
}

function newSessionId(): string {
  try {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
      return crypto.randomUUID();
    }
  } catch {
  }
  return `sid-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function getSessionId(): string | null {
  try {
    return localStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

export function setSessionId(id: string): void {
  try {
    localStorage.setItem(SESSION_KEY, id);
  } catch {
  }
}

export function clearSessionId(): void {
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch {
  }
}

export function ensureSessionId(): string {
  let id = getSessionId();
  if (!id) {
    id = newSessionId();
    setSessionId(id);
  }
  return id;
}

export function regenerateSessionId(): string {
  clearSessionId();
  const id = newSessionId();
  setSessionId(id);
  return id;
}

const USER_DOC_KEY_PREFIX = "docmind_user_doc_key:";

export function getUserDocKey(username: string): string {
  const storageKey = `${USER_DOC_KEY_PREFIX}${username}`;
  try {
    const existing = localStorage.getItem(storageKey);
    if (existing) return existing;
    const id = newSessionId();
    localStorage.setItem(storageKey, id);
    return id;
  } catch {
    return `user-${username}`;
  }
}

export function authHeader(): Record<string, string> {
  const headers: Record<string, string> = { "X-Session-Id": ensureSessionId() };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export function decodeJwt(token: string): { sub?: string; exp?: number } | null {
  try {
    const payload = token.split(".")[1];
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string | null = getToken()): boolean {
  if (!token) return true;
  const payload = decodeJwt(token);
  if (!payload?.exp) return true;
  return payload.exp * 1000 <= Date.now();
}

export function notifyUnauthorized(): void {
  window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
}

export function notifyRateLimited(retryAfter: number): void {
  window.dispatchEvent(
    new CustomEvent(RATE_LIMITED_EVENT, { detail: { retryAfter } }),
  );
}
