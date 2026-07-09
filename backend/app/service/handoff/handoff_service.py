import os
import json
import smtplib
import datetime
import secrets
from email.mime.text import MIMEText
from typing import Dict, Any, Optional, List

from ...config.config import logger


HANDOFF_FAITHFULNESS_THRESHOLD = float(os.getenv("HANDOFF_FAITHFULNESS_THRESHOLD", "0.6"))
HANDOFF_RELEVANCE_THRESHOLD = float(os.getenv("HANDOFF_RELEVANCE_THRESHOLD", "0.3"))

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("APPLICATION_EMAIL")
EMAIL_TO = os.getenv("SUPPORT_EMAIL")


_EXPLICIT_KEYWORDS = (
    "human agent",
    "human support",
    "real person",
    "real human",
    "speak to a human",
    "talk to a human",
    "speak with a human",
    "talk to a person",
    "speak to someone",
    "live agent",
    "customer support",
    "escalate to a human",
    "escalate this",
    "talk to support",
    "contact support",
    "human representative",
)


def generate_handoff_reference_id(now: Optional[datetime.datetime] = None) -> str:
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    return f"HO-{timestamp}-{secrets.token_hex(3).upper()}"


def evaluate_handoff_trigger(
    faithfulness: Optional[float],relevance: Optional[float],
    user_question: str,
    no_context: bool,
) -> Dict[str, Any]:
    question_lower = (user_question or "").lower()

    # 1. User explicitly asked for a human -> highest priority.
    if any(kw in question_lower for kw in _EXPLICIT_KEYWORDS):
        return {"trigger": True, "reason": "explicit user request for a human", "priority": "high"}

    # 2. Nothing retrieved -> the agent had no grounding at all.
    if no_context:
        return {"trigger": True, "reason": "retrieval returned no grounding context", "priority": "high"}

    # 3. Answer not grounded in retrieved context (ragas faithfulness).
    if (
        faithfulness is not None
        and faithfulness < HANDOFF_FAITHFULNESS_THRESHOLD
        and (relevance is None or relevance < HANDOFF_RELEVANCE_THRESHOLD)
    ):
        return {
            "trigger": True,
            "reason": f"faithfulness {faithfulness} below threshold {HANDOFF_FAITHFULNESS_THRESHOLD}",
            "priority": "normal",
        }

    if relevance is not None and relevance < HANDOFF_RELEVANCE_THRESHOLD:
        return {
            "trigger": True,
            "reason": f"answer relevance {relevance} below threshold {HANDOFF_RELEVANCE_THRESHOLD}",
            "priority": "normal",
        }
    return {"trigger": False, "reason": "", "priority": "normal"}


def _smtp_missing() -> List[str]:
    return [
        name for name, value in (
            ("SMTP_HOST", SMTP_HOST),
            ("SMTP_USERNAME", SMTP_USERNAME),
            ("SMTP_PASSWORD", SMTP_PASSWORD),
            ("APPLICATION_EMAIL", EMAIL_FROM),
            ("SUPPORT_EMAIL", EMAIL_TO),
        ) if not value
    ]


def send_handoff_email(context: Dict[str, Any]) -> None:
    missing = _smtp_missing()
    if missing:
        logger.warning(
            "SMTP configuration incomplete (%s); handoff e-mail skipped "
            "(ref=%s). The handoff was still detected and shown to the user.",
            ", ".join(missing), context.get("reference_id", "N/A"),
        )
        return

    reference_id = context.get("reference_id", "N/A")
    trace_id = context.get("trace_id", "N/A")
    timestamp = context.get("timestamp", "N/A")
    priority = context.get("priority", "normal")
    trigger_reason = context.get("trigger_reason", "N/A")
    user_metadata = context.get("user_metadata", {})
    query_history = context.get("query_history", [])
    generated_answer = context.get("generated_answer", "")
    evaluation_scores = context.get("evaluation_scores", {})
    retrieved_chunks = context.get("retrieved_chunks", [])
    tools_used = context.get("tools_used", [])

    subject = f"[HUMAN HANDOFF] Ref {reference_id} – {trigger_reason}"

    def _fmt(value: Any) -> str:
        return json.dumps(value, indent=2, default=str)

    body = f"""A conversation has been escalated for human handoff.

Reference ID:   {reference_id}
Trace ID:       {trace_id}
Timestamp:      {timestamp}
Priority:       {priority}
Trigger Reason: {trigger_reason}

--- User Metadata ---
{_fmt(user_metadata)}

--- Query History ---
{_fmt(query_history)}

--- Tools Used ---
{_fmt(tools_used)}

--- Generated Answer ---
{generated_answer}

--- Evaluation Scores (ragas) ---
{_fmt(evaluation_scores)}

--- Retrieved Chunks ---
{_fmt(retrieved_chunks)}

Open the full trace in Langfuse using the Trace ID above.
"""

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(
            "Handoff e-mail sent (ref=%s, priority=%s) to %s",
            reference_id, priority, EMAIL_TO,
        )
    except Exception as e:
        logger.error(f"Failed to send handoff e-mail (ref={reference_id}): {e}", exc_info=True)
