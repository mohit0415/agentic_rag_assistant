"""Human-handoff package: escalates low-quality / explicitly-requested turns
to a human support agent via email, reusing the existing ragas scores."""

from .handoff_service import (
    generate_handoff_reference_id,
    evaluate_handoff_trigger,
    send_handoff_email,
)

__all__ = [
    "generate_handoff_reference_id",
    "evaluate_handoff_trigger",
    "send_handoff_email",
]
