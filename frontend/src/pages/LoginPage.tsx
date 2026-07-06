import React, { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  Eye,
  EyeOff,
  ExternalLink,
  HeartPulse,
  ImageIcon,
  KeyRound,
  Loader2,
  Lock,
  ShieldCheck,
  Sparkles,
  Table2,
  User,
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../utils/network";
import StringData from "../StringData";

const Step: React.FC<{ n: number; children: React.ReactNode }> = ({ n, children }) => (
  <li className="flex gap-2.5">
    <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-accent/10 text-[10.5px] font-semibold text-accent">
      {n}
    </span>
    <span className="text-[12.5px] leading-relaxed text-txt-sec">{children}</span>
  </li>
);

const GuideLink: React.FC<{ href: string; children: React.ReactNode }> = ({ href, children }) => (
  <a
    href={href}
    target="_blank"
    rel="noreferrer"
    className="inline-flex items-center gap-1 font-medium text-accent hover:underline"
  >
    {children}
    <ExternalLink size={11} />
  </a>
);

const KeySetupGuide: React.FC = () => (
  <div className="relative flex h-full w-full items-center overflow-hidden">
    <div
      className="pointer-events-none absolute -top-32 -left-24 h-[420px] w-[420px] rounded-full opacity-25 blur-3xl"
      style={{ background: "radial-gradient(circle, #22D3EE 0%, transparent 70%)" }}
    />
    <div
      className="pointer-events-none absolute bottom-[-140px] right-[-80px] h-[460px] w-[460px] rounded-full opacity-20 blur-3xl"
      style={{ background: "radial-gradient(circle, #3B82F6 0%, transparent 70%)" }}
    />

    <div className="relative mx-auto w-full max-w-[520px] space-y-5 px-10 py-12">
      <div>
        <div className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-line bg-white/[0.04] px-3 py-1 text-[11px] font-medium text-txt-sec backdrop-blur">
          <Sparkles size={12} className="text-accent" />
          Before you sign in
        </div>
        <h2 className="font-display text-[24px] font-semibold leading-snug tracking-tight text-txt-pri">
          Set up your{" "}
          <span className="bg-gradient-to-r from-[#22D3EE] to-[#3B82F6] bg-clip-text text-transparent">
            API keys
          </span>
        </h2>
      </div>

      <div className="rounded-2xl border border-line bg-card/70 p-5 shadow-card backdrop-blur-md">
        <div className="mb-2 flex items-center justify-between">
          <span className="flex items-center gap-2 text-[13px] font-semibold text-txt-pri">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#22D3EE]/10 text-accent">
              <KeyRound size={14} />
            </span>
            Gemini API key
          </span>
          <span className="rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-success">
            Configured on server
          </span>
        </div>
        <p className="text-[12.5px] leading-relaxed text-txt-sec">
          The LLM + embedding key is managed by the server administrator (set via{" "}
          <code className="text-accent">GEMINI_API_KEY</code> in the backend environment). You
          don't need to provide it here.
        </p>
      </div>

      <div className="rounded-2xl border border-line bg-card/70 p-5 shadow-card backdrop-blur-md">
        <div className="mb-3 flex items-center justify-between">
          <span className="flex items-center gap-2 text-[13px] font-semibold text-txt-pri">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#8B5CF6]/10 text-[#A78BFA]">
              <Table2 size={14} />
            </span>
            LlamaParse key (LLAMA_CLOUD_API_KEY)
          </span>
        </div>
        <ol className="space-y-2">
          <Step n={1}>
            Go to <GuideLink href="https://cloud.llamaindex.ai">cloud.llamaindex.ai</GuideLink> and
            sign in (Google / GitHub / email).
          </Step>
          <Step n={2}>
            In the left menu open <b className="text-txt-pri">API Keys</b> →{" "}
            <b className="text-txt-pri">Generate New Key</b>.
          </Step>
          <Step n={3}>
            Copy the key (starts with <code className="text-accent">llx-…</code>) and paste it into
            the form.
          </Step>
        </ol>
      </div>

      <div className="flex gap-3 rounded-2xl border border-warning/25 bg-warning/[0.06] p-4 backdrop-blur-md">
        <AlertTriangle size={16} className="mt-0.5 flex-shrink-0 text-[#FBBF24]" />
        <p className="text-[12px] leading-relaxed text-txt-sec">
          <b className="text-txt-pri">Multimodal documents:</b> if an uploaded document contains{" "}
          <span className="inline-flex items-center gap-1 text-txt-pri">
            <Table2 size={11} /> tables
          </span>{" "}
          or{" "}
          <span className="inline-flex items-center gap-1 text-txt-pri">
            <ImageIcon size={11} /> images
          </span>
          , it is parsed with LlamaParse — those uploads <b className="text-txt-pri">fail without
          a LlamaParse key</b>. Plain-text documents index fine without it.
        </p>
      </div>
    </div>
  </div>
);

const LoginPage: React.FC = () => {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [llamaparseApiKey, setLlamaparseApiKey] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showKeys, setShowKeys] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as { from?: string } | null)?.from || "/";

  if (isAuthenticated) {
    navigate(from, { replace: true });
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password, {
        llamaparseApiKey: llamaparseApiKey.trim() || undefined,
      });
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative flex min-h-screen overflow-hidden bg-ink font-sans text-txt-pri">
      <div className="relative hidden w-[52%] border-r border-line lg:block">
        <KeySetupGuide />
      </div>

      <div className="relative flex flex-1 items-center justify-center px-4 py-10 sm:px-8">
        <div
          className="pointer-events-none absolute -top-32 right-[-120px] h-96 w-96 rounded-full opacity-15 blur-3xl"
          style={{ background: "radial-gradient(circle, #22D3EE 0%, transparent 70%)" }}
        />
        <div
          className="pointer-events-none absolute -bottom-40 left-[-100px] h-96 w-96 rounded-full opacity-10 blur-3xl"
          style={{ background: "radial-gradient(circle, #3B82F6 0%, transparent 70%)" }}
        />

        <div className="relative w-full max-w-[400px] animate-rise-in">
          <div className="mb-8 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-[#22D3EE] to-[#3B82F6] text-[#04121A] shadow-glow-soft">
              <HeartPulse size={26} strokeWidth={2.2} />
            </div>
            <h1 className="font-display text-[24px] font-semibold tracking-tight">
              Med
              <span className="bg-gradient-to-r from-[#22D3EE] to-[#3B82F6] bg-clip-text text-transparent">
                {StringData.app.nameHighlight}
              </span>{" "}
              Assistant
            </h1>
            <p className="mt-1.5 text-[13px] text-txt-mut">{StringData.app.tagline}</p>
          </div>

          <form
            onSubmit={handleSubmit}
            className="rounded-modal border border-line bg-card/60 p-7 shadow-modal backdrop-blur-xl"
          >
            <h2 className="mb-1 text-[17px] font-semibold text-txt-pri">Welcome back</h2>
            <p className="mb-6 text-[12.5px] text-txt-mut">
              Sign in to your clinical research workspace.
            </p>

            <label className="ml-label mb-1.5 block">Username</label>
            <div className="relative mb-4">
              <User size={15} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-txt-mut" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
                placeholder="dr.mohit sai kumar"
                className="ml-input pl-10"
              />
            </div>

            <label className="ml-label mb-1.5 block">Password</label>
            <div className="relative mb-2">
              <Lock size={15} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-txt-mut" />
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                placeholder="••••••••"
                className="ml-input pl-10 pr-11"
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                className="absolute right-2.5 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-lg text-txt-mut transition-colors hover:bg-white/[0.06] hover:text-accent"
                tabIndex={-1}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>

            <div className="mb-1 mt-5 flex items-center justify-between">
              <span className="ml-label inline-flex items-center gap-1.5">
                <KeyRound size={11} className="text-txt-mut" />
                Provider keys
              </span>
              <button
                type="button"
                onClick={() => setShowKeys((s) => !s)}
                className="rounded-lg px-2 py-1 text-[11px] font-medium text-txt-mut transition-colors hover:text-accent"
                tabIndex={-1}
              >
                {showKeys ? "Hide" : "Show"}
              </button>
            </div>

            <label className="ml-label mb-1.5 block">
              LlamaParse API key
              <span className="ml-1 font-normal normal-case tracking-normal text-txt-mut/70">
                · tables &amp; diagrams
              </span>
            </label>
            <input
              type={showKeys ? "text" : "password"}
              value={llamaparseApiKey}
              onChange={(e) => setLlamaparseApiKey(e.target.value)}
              autoComplete="off"
              placeholder="llx-…"
              className="ml-input mb-1"
            />
            <p className="mb-1 text-[11px] leading-relaxed text-txt-mut/80">
              Needed only for documents containing tables or images (get it at{" "}
              <a href="https://cloud.llamaindex.ai" target="_blank" rel="noreferrer" className="text-accent hover:underline">
                cloud.llamaindex.ai
              </a>
              ).
            </p>
            <p className="mb-2 flex items-center gap-1.5 text-[11px] text-txt-mut/80">
              <ShieldCheck size={12} className="flex-shrink-0 text-success/80" />
              Keys are carried securely inside your signed session token.
            </p>

            {error && (
              <div className="mb-4 mt-2 animate-fade-in rounded-xl border border-danger/30 bg-danger/10 px-3.5 py-2.5 text-[12px] text-[#FCA5A5]">
                {error}
              </div>
            )}

            <button type="submit" disabled={submitting} className="btn-primary mt-4 w-full py-3">
              {submitting ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  Signing in…
                </>
              ) : (
                <>
                  <Activity size={15} />
                  Sign in to MedLearn
                </>
              )}
            </button>
          </form>

          <p className="mt-6 flex items-center justify-center gap-1.5 text-center text-[11px] text-txt-mut/80">
            <Lock size={11} />
            Protected by JWT · sessions expire automatically
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
