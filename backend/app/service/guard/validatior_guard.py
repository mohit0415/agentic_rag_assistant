


from typing import List, Tuple
import re
import threading

_SQL_LIKE_PATTERN = re.compile(
    r"\b(insert\s+into|delete\s+from|drop\s+table|truncate\s+table|"
    r"update\s+\S+\s+set|alter\s+table|create\s+table)\b",
    re.IGNORECASE,
)

_MUTATION_VERBS = r"(insert|delete|remove|drop|update|modify|alter|overwrite|truncate|add|create)"
_DB_NOUNS = r"(record|records|row|rows|entry|entries|table|tables|database|databases|db|column|columns|schema)"


_MUTATION_INTENT_PATTERN = re.compile(
    rf"\b{_MUTATION_VERBS}\b(?:\s+\S+){{0,3}}\s+\b{_DB_NOUNS}\b"
    rf"|\b{_DB_NOUNS}\b(?:\s+\S+){{0,3}}\s+\b{_MUTATION_VERBS}\b",
    re.IGNORECASE,
)


_SQL_INTENT_LABELS = [
    "SELECT", "INSERT", "UPDATE", "DELETE", "DROP",
    "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE", "OTHER",
]
_BLOCKED_SQL_INTENTS = {
    "INSERT", "UPDATE", "DELETE", "DROP",
    "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE",
}

_SQL_INTENT_PROMPT = """You are a strict SQL-intent classifier sitting in front of a hospital database tool.

Read the natural-language question below and decide which single SQL operation it is really asking the database to perform, however it is phrased.

Respond with EXACTLY ONE WORD from this fixed list, and nothing else:
SELECT, INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, OTHER

Guidance:
- Looking up / retrieving / counting / comparing / reading data -> SELECT
- Adding new rows or records (however phrased, e.g. "make a new entry") -> INSERT
- Changing or editing existing data (however phrased, e.g. "fix", "correct", "set X to Y") -> UPDATE
- Removing rows or records (however phrased, e.g. "erase", "wipe", "get rid of", "purge") -> DELETE
- Removing a table or schema entirely -> DROP
- Changing table/column structure -> ALTER
- Emptying a table -> TRUNCATE
- Creating a new table/schema -> CREATE
- Granting/revoking permissions -> GRANT or REVOKE
- Anything else, or unclear -> OTHER

Question: {query}

One-word classification:"""


class GuardrailsValidator:

    
    def __init__(self):
    
        try:
            from guardrails import Guard
            from guardrails.hub import DetectPII
            import os
            _default_entities = [
                "EMAIL_ADDRESS",
                "PHONE_NUMBER",
                "CREDIT_CARD",
                "US_SSN",           
                "US_BANK_NUMBER",   
                "US_ITIN",          
                "MEDICAL_LICENSE", 
            ]
            _env_entities = os.getenv("PII_ENTITIES", "").strip()
            pii_entities = (
                [e.strip() for e in _env_entities.split(",") if e.strip()]
                if _env_entities else _default_entities
            )

            self.pii_guard = Guard().use(
                DetectPII(
                    pii_entities=pii_entities,
                    on_fail="fix"  # Automatically redact PII
                )
            )
            
            print("✓ LOCAL Guardrails validators initialized:")
            print("  - DetectPII (Output validation - PII detection & redaction)")
            print("  Note: 'Could not obtain event loop' warning is harmless")
            
        except ImportError as e:
            print("\n" + "="*70)
            print("ERROR: Guardrails Hub validators not installed!")
            print("="*70)
            print("\nPlease run the following commands:")
            print("\n1. Configure Guardrails:")
            print("   guardrails configure")
            print("\n2. Install LOCAL validators (no API key needed):")
            print("   guardrails hub install hub://guardrails/detect_pii")
            print("\n" + "="*70 + "\n")
            raise ImportError(f"Guardrails Hub validators not installed: {e}")
    
    def validate_input(self, text: str) -> Tuple[bool, str]:
        if not text or not text.strip():
            return False, "Input text cannot be empty"
        return True, None

    def validate_query_intent(self, text: str) -> Tuple[bool, str]:
        if not text:
            return True, None

        if _SQL_LIKE_PATTERN.search(text):
            return False, (
                "Query blocked: this looks like a request to modify the database "
                "(insert/update/delete/drop/etc.). Only read-only questions are supported."
            )

        if _MUTATION_INTENT_PATTERN.search(text):
            return False, (
                "Query blocked: this looks like a request to add, change, or remove "
                "data (e.g. a record/row/table). Only read-only questions are supported."
            )

        return True, None

    def validate_sql_intent_with_llm(self, llm, query: str) -> Tuple[bool, str]:
        if not query or not query.strip():
            return True, None

        try:
            prompt = _SQL_INTENT_PROMPT.format(query=query)
            raw = str(llm.complete(prompt)).strip().upper()
        except Exception as e:
            print(f"⚠ SQL intent classification failed, blocking query: {e}")
            return False, f"Query blocked: could not verify query safety ({e})."

        label = None
        for candidate in _BLOCKED_SQL_INTENTS:
            if re.search(rf"\b{candidate}\b", raw):
                label = candidate
                break
        if label is None:
            label = "SELECT" if re.search(r"\bSELECT\b", raw) else "OTHER"

        if label in _BLOCKED_SQL_INTENTS:
            return False, (
                f"Query blocked: classified as a {label} operation. "
                "Only read-only SELECT queries are allowed."
            )

        return True, None

    def validate_output(
        self, 
        text: str, 
        check_pii: bool = True
    ) -> Tuple[bool, str, List[str]]:
        pii_summaries = []
        sanitized_text = text
        
        if check_pii:
            try:
                print(f"🔍 Checking output for PII (LOCAL Presidio detection)...")
                result = self.pii_guard.validate(text)
                sanitized_text = result.validated_output if result.validated_output else text
                
                if sanitized_text != text:
                    pii_summaries.append("PII detected and redacted by LOCAL Presidio analyzer")
                    print(f"⚠ PII detected and redacted")
                else:
                    print(f"✓ No PII detected in output")
                    
            except Exception as e:
                print(f"⚠ PII detection failed, withholding output (fail-closed): {e}")
                pii_summaries.append(f"PII check failed, output withheld: {e}")
                return False, (
                    "The response was withheld because the PII safety check "
                    "could not be completed. Please try again."
                ), pii_summaries

        return True, sanitized_text, pii_summaries



_validator_instance: "GuardrailsValidator | None" = None
_validator_lock = threading.Lock()


def get_guardrails_validator() -> "GuardrailsValidator":
    global _validator_instance
    if _validator_instance is None:
        with _validator_lock:
            if _validator_instance is None:
                _validator_instance = GuardrailsValidator()
    return _validator_instance
    
 