
export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8000";

export const API_PREFIX = "/api";

export const ENDPOINTS = {
  query: `${API_PREFIX}/query`,
  upload: `${API_PREFIX}/upload`,
  login: `${API_PREFIX}/login`,
  me: `${API_PREFIX}/me`,
  models: `${API_PREFIX}/models`,
  provider: `${API_PREFIX}/provider`,
} as const;

export const URLS = {
  query: `${API_BASE_URL}${ENDPOINTS.query}`,
  upload: `${API_BASE_URL}${ENDPOINTS.upload}`,
  login: `${API_BASE_URL}${ENDPOINTS.login}`,
  me: `${API_BASE_URL}${ENDPOINTS.me}`,
  models: `${API_BASE_URL}${ENDPOINTS.models}`,
  provider: `${API_BASE_URL}${ENDPOINTS.provider}`,
} as const;

export default URLS;
