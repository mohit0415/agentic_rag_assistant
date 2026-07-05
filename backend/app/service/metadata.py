from llama_index.core import Document
import json
import os
from llama_index.llms.azure_openai import AzureOpenAI
from datetime import datetime, timezone

ALLOWED_CATEGORIES = ["report", "manual", "article", "contract", "research_paper", "personal_notes", "other"]


DOMAIN = "medical_education"

ALLOWED_SOURCE_TYPES = [
    "textbook",                    
    "anatomy_physiology_textbook",
    "clinical_database",          
    "research_paper",             
    "pubmed_article",             
    "other",
]


ALLOWED_SPECIALTIES = [
    "anatomy", "physiology", "pathology", "pharmacology",
    "neuroscience", "clinical_medicine", "general_medicine", "other",
]


ALLOWED_SYSTEMS = [
    "somatosensory_system", "nervous_system", "cardiovascular_system",
    "respiratory_system", "musculoskeletal_system", "endocrine_system",
    "digestive_system", "renal_system", "not_applicable",
]


ALLOWED_CONTENT_DOMAINS = ["conceptual", "clinical_fact", "mixed"]
ALLOWED_ROUTES = ["rag", "sql", "hybrid"]


class DocumentMetadataExtractor:
    def __init__(self, doc: Document, llm: AzureOpenAI, file_path: str, original_filename: str, uploaded_by: str = "Mohit"):
        self.doc = doc
        self.file_path = file_path
        self.uploaded_by = uploaded_by
        self.llm = llm
        self.original_filename = original_filename

    def _infer_source_type(self) -> str:
        name = (self.original_filename or os.path.basename(self.file_path) or "").lower()
        if "pubmed" in name:
            return "pubmed_article"
        if any(k in name for k in ("drug", "interaction", "lab", "range", "contraindication", "clinical_db", "database")):
            return "clinical_database"
        if any(k in name for k in ("anatomy", "physiology", "somatosensory")):
            return "anatomy_physiology_textbook"
        if any(k in name for k in ("paper", "journal", "study", "research")):
            return "research_paper"
        return "textbook"

    def build_structural_metadata(self, parsed_with: str = "llamaindex") -> dict:
        return {
            "original_file_name": self.original_filename,
            "file_name": os.path.basename(self.file_path),
            "file_type": os.path.splitext(self.file_path)[1].replace(".", ""),
            "upload_date": datetime.now(timezone.utc).isoformat(),
            "uploaded_by": self.uploaded_by,
            "file_size_kb": round(os.path.getsize(self.file_path) / 1024, 1),
            "domain": DOMAIN,
            "source_type": self._infer_source_type(),
            "parsed_with": parsed_with,
            "level": "document",
        }

    def extract_content_metadata(self) -> dict:
        excerpt = self.doc.text[:3000]
        prompt = f"""Read this document excerpt and return JSON with exactly these fields:
        - "doc_category": exactly one of {ALLOWED_CATEGORIES}
        - "topic": a short 1-3 word general subject
        - "keywords": a list of 3-5 specific keywords
        - "summary": one sentence summary

        Excerpt: {excerpt}

        Return only valid JSON, no markdown fences, no preamble."""

        raw = self.llm.complete(prompt).text.strip()
        try:
            extracted = json.loads(raw)
        except json.JSONDecodeError:
            cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            try:
                extracted = json.loads(cleaned)
            except json.JSONDecodeError:
                extracted = {"doc_category": "other", "topic": "unknown", "keywords": [], "summary": ""}

        if extracted.get("doc_category") not in ALLOWED_CATEGORIES:
            extracted["doc_category"] = "other"
        return extracted

    def extract_medical_metadata(self) -> dict:
        excerpt = (self.doc.text or "")[:3000]
        prompt = f"""You are tagging a chunk of a MEDICAL EDUCATION corpus
        (anatomy & physiology textbooks, the somatosensory system chapter, and
        structured clinical data such as drug interactions and lab ranges).
        Read the excerpt and return JSON with exactly these fields:
        - "source_type": one of {ALLOWED_SOURCE_TYPES}
        - "medical_specialty": one of {ALLOWED_SPECIALTIES}
        - "anatomical_system": one of {ALLOWED_SYSTEMS}
        - "content_domain": one of {ALLOWED_CONTENT_DOMAINS} (conceptual = explanatory textbook prose, clinical_fact = deterministic facts/figures like lab ranges or drug interactions)
        - "intended_route": one of {ALLOWED_ROUTES} (rag for conceptual, sql for deterministic facts, hybrid for both)

        Excerpt: {excerpt}

        Return only valid JSON, no markdown fences, no preamble."""

        defaults = {
            "medical_specialty": "other",
            "anatomical_system": "not_applicable",
            "content_domain": "conceptual",
            "intended_route": "rag",
        }
        try:
            raw = self.llm.complete(prompt).text.strip()
            try:
                extracted = json.loads(raw)
            except json.JSONDecodeError:
                cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                extracted = json.loads(cleaned)
        except Exception:
            extracted = {}
        out = {}
        out["medical_specialty"] = extracted.get("medical_specialty") if extracted.get("medical_specialty") in ALLOWED_SPECIALTIES else defaults["medical_specialty"]
        out["anatomical_system"] = extracted.get("anatomical_system") if extracted.get("anatomical_system") in ALLOWED_SYSTEMS else defaults["anatomical_system"]
        out["content_domain"] = extracted.get("content_domain") if extracted.get("content_domain") in ALLOWED_CONTENT_DOMAINS else defaults["content_domain"]
        out["intended_route"] = extracted.get("intended_route") if extracted.get("intended_route") in ALLOWED_ROUTES else defaults["intended_route"]
        if extracted.get("source_type") in ALLOWED_SOURCE_TYPES:
            out["source_type"] = extracted["source_type"]
        return out


    def build_document_metadata(self, parsed_with: str = "llamaindex", include_medical: bool = True) -> dict:
        meta = self.build_structural_metadata(parsed_with=parsed_with)
        try:
            content = self.extract_content_metadata()
            meta["doc_category"] = content.get("doc_category", "other")
            meta["topic"] = content.get("topic", "unknown")
            meta["keywords"] = content.get("keywords", [])
            meta["summary"] = content.get("summary", "")
        except Exception:
            pass
        if include_medical:
            meta.update(self.extract_medical_metadata())
        return meta
    
    def enrich(self) -> Document:
        structural = self.build_structural_metadata(parsed_with="llamaindex")
        content = self.extract_content_metadata()

        self.doc.metadata.update(structural)
        self.doc.metadata["doc_category"] = content["doc_category"]
        self.doc.metadata["topic"] = content["topic"]
        self.doc.metadata["keywords"] = content["keywords"]
        self.doc.metadata["summary"] = content["summary"]
        self.doc.metadata.update(self.extract_medical_metadata())

        return self.doc
