import { authHeader, notifyRateLimited, notifyUnauthorized } from "../auth/token";
import { formatCountdown } from "./time";

export class ApiError extends Error {
  status: number;
  detail?: string;
  retryAfter?: number;

  constructor(message: string, status = 0, detail?: string, retryAfter?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.retryAfter = retryAfter;
  }
}

function networkError(e: unknown): ApiError {
  const original = e instanceof Error ? `${e.name}: ${e.message}` : String(e);
  return new ApiError(
    `Network error — is the server running? (${original})`,
    0,
    original,
  );
}

function parseRetryAfter(res: Response, fallback = 60): number {
  const raw = res.headers.get("Retry-After");
  const n = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

async function handleRateLimited(res: Response): Promise<ApiError> {
  const retryAfter = parseRetryAfter(res);
  notifyRateLimited(retryAfter);
  const friendly = `Rate limit reached. Come back in ${formatCountdown(retryAfter)}.`;
  return new ApiError(friendly, 429, undefined, retryAfter);
}

async function extractErrorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail) && data.detail[0]?.msg) return data.detail[0].msg;
    if (typeof data?.error === "string") return data.error;
  } catch {
  }
  return `Request failed with status ${res.status}`;
}

export interface UploadResponse {
  message: string;
  documents_indexed: number;
}

export async function uploadFile(url: string, file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);

  let res: Response;
  try {
    res = await fetch(url, { method: "POST", body: form, headers: { ...authHeader() } });
  } catch (e) {
    throw networkError(e);
  }

  if (res.status === 401) {
    notifyUnauthorized();
    throw new ApiError(await extractErrorMessage(res), 401);
  }
  if (res.status === 429) {
    throw await handleRateLimited(res);
  }
  if (!res.ok) {
    throw new ApiError(await extractErrorMessage(res), res.status);
  }
  return (await res.json()) as UploadResponse;
}

export interface SSEHandlers {
  onEvent: (event: string, data: any) => void;
  onClose?: () => void;
}

export async function streamSSE(
  url: string,
  body: unknown,
  handlers: SSEHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...authHeader(),
      },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if ((e as any)?.name === "AbortError") return;
    throw networkError(e);
  }

  if (res.status === 401) {
    notifyUnauthorized();
    throw new ApiError(await extractErrorMessage(res), 401);
  }
  if (res.status === 429) {
    throw await handleRateLimited(res);
  }
  if (!res.ok) {
    throw new ApiError(await extractErrorMessage(res), res.status);
  }
  if (!res.body) {
    throw new ApiError("Streaming not supported by this response", res.status);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const rawFrame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        dispatchFrame(rawFrame, handlers);
      }
    }
    if (buffer.trim()) dispatchFrame(buffer, handlers);
  } finally {
    reader.releaseLock();
  }

  handlers.onClose?.();
}

function dispatchFrame(rawFrame: string, handlers: SSEHandlers): void {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of rawFrame.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (dataLines.length === 0) return;

  const dataStr = dataLines.join("\n");
  let data: any = dataStr;
  try {
    data = JSON.parse(dataStr);
  } catch {
  }
  handlers.onEvent(event, data);
}
