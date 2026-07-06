import { useCallback, useRef, useState } from "react";
import URLS, { API_BASE_URL } from "../config/urls";
import { streamSSE, ApiError } from "../utils/network";
import {
  parseSources,
  PipelineStep,
  SourceItem,
  TableAttachment,
  ImageAttachment,
} from "../types";
import { EvalScores } from "../components/EvalScorePanel";
import StringData from "../StringData";

export interface Citation {
  chunkIndex: number;
  label: string;
}

export interface SourceChip {
  chunkIndex: number;
  label: string;
  icon: string;
}

export interface Message {
  id: string;
  role: "ai" | "user";
  content: string;
  citations?: Citation[];
  sources?: SourceChip[];
  toolsUsed?: string[];
  tables?: TableAttachment[];
  images?: ImageAttachment[];
  streaming?: boolean;
  error?: boolean;
}

function resolveImages(images?: ImageAttachment[] | null): ImageAttachment[] {
  if (!Array.isArray(images)) return [];
  return images.map((img) => ({
    ...img,
    url: /^https?:\/\//.test(img.url) ? img.url : `${API_BASE_URL}${img.url}`,
  }));
}

function extractCitations(text: string): Citation[] {
  const found = new Map<number, Citation>();
  const re = /\[(\d+)\]/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const n = Number(m[1]);
    if (!found.has(n)) found.set(n, { chunkIndex: n, label: String(n) });
  }
  return [...found.values()].sort((a, b) => a.chunkIndex - b.chunkIndex);
}

function sourcesToChips(sources: SourceItem[]): SourceChip[] {
  return sources.map((s) => ({
    chunkIndex: s.index,
    label: `[${s.index}] ${s.fileName}`,
    icon: "📄",
  }));
}

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "ai",
  content: StringData.chat.welcomeMessage
    .replace("{count}", "3")
    .replace("{chunks}", "1,159"),
};

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [isThinking, setIsThinking] = useState(false);
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([]);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [toolsUsed, setToolsUsed] = useState<string[]>([]);
  const [evalScores, setEvalScores] = useState<EvalScores>({
    faithfulness: null,
    relevance: null,
  });
  const abortRef = useRef<AbortController | null>(null);

  const upsertStep = useCallback((step: PipelineStep) => {
    setPipelineSteps((prev) => {
      const idx = prev.findIndex((s) => s.id === step.id);
      const next = prev.map((s) =>
        s.status === "active" && s.id !== step.id ? { ...s, status: "done" as const } : s,
      );
      if (idx === -1) return [...next, step];
      next[idx] = step;
      return next;
    });
  }, []);

  const patchMessage = useCallback((id: string, patch: Partial<Message>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));
  }, []);

  const sendQuestion = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || isThinking) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const userMsg: Message = { id: `user-${Date.now()}`, role: "user", content: trimmed };
      const aiId = `ai-${Date.now()}`;
      const aiMsg: Message = { id: aiId, role: "ai", content: "", streaming: true };

      setMessages((prev) => [...prev, userMsg, aiMsg]);
      setIsThinking(true);
      setPipelineSteps([]);
      setSources([]);
      setToolsUsed([]);
      setEvalScores({ faithfulness: null, relevance: null });

      let answerBuffer = "";

      try {
        await streamSSE(
          URLS.query,
          { question: trimmed },
          {
            onEvent: (event, data) => {
              switch (event) {
                case "step":
                  upsertStep(data as PipelineStep);
                  break;
                case "token":
                  answerBuffer += data?.text ?? "";
                  patchMessage(aiId, { content: answerBuffer });
                  break;
                case "meta": {
                  const finalAnswer = data?.answer || answerBuffer;
                  const parsedSources = parseSources(data?.sources_used);
                  const tools = Array.isArray(data?.tools_used) ? data.tools_used : [];
                  setSources(parsedSources);
                  setToolsUsed(tools);
                  setEvalScores({
                    faithfulness:
                      typeof data?.faithfulness_score === "number"
                        ? data.faithfulness_score
                        : null,
                    relevance:
                      typeof data?.relevance_score === "number"
                        ? data.relevance_score
                        : null,
                  });
                  patchMessage(aiId, {
                    content: finalAnswer,
                    citations: extractCitations(finalAnswer),
                    sources: sourcesToChips(parsedSources),
                    toolsUsed: tools,
                    tables: Array.isArray(data?.tables) ? data.tables : [],
                    images: resolveImages(data?.images),
                  });
                  break;
                }
                case "error":
                  patchMessage(aiId, {
                    content: data?.detail || StringData.errors.queryFailed,
                    error: true,
                    streaming: false,
                  });
                  break;
                default:
                  break;
              }
            },
            onClose: () => {
              patchMessage(aiId, { streaming: false });
            },
          },
          controller.signal,
        );
      } catch (e) {
        const detail =
          e instanceof ApiError ? e.message : StringData.errors.queryFailed;
        patchMessage(aiId, { content: detail, error: true, streaming: false });
      } finally {
        setIsThinking(false);
        abortRef.current = null;
      }
    },
    [isThinking, patchMessage, upsertStep],
  );

  return { messages, isThinking, pipelineSteps, sources, toolsUsed, evalScores, sendQuestion };
}

export default useChat;
