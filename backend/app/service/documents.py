import re
import tempfile
import unicodedata
from typing import List, Tuple

from llama_index.core import Document
from llama_index.core.readers import SimpleDirectoryReader


MIN_TEXT_LENGTH = 50

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def clean_extracted_text(text: str) -> str:

    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\x00", "")
    text = _CONTROL_CHARS.sub("", text)
    return text


class Document_Process:
    def __init__(self, data: bytes, file_ext: str = '.pdf'):
        self.content = data
        self.file_ext = file_ext

    def process_docs(self) -> Tuple[List[Document], str]:
        with tempfile.NamedTemporaryFile(
            mode='wb',
            suffix=self.file_ext,
            delete=False,
        ) as tmp_file:
            tmp_file.write(self.content)
            file_path = tmp_file.name

        documents = _load_with_llamaindex(file_path)
        return documents, file_path



_BINARY_SIGNATURES = ("%PDF-", "PK\x03\x04", "\xff\xd8\xff", "\x89PNG")


def _assert_not_raw_binary(documents: List[Document]) -> None:
    for doc in documents:
        head = (doc.text or "").lstrip()[:8]
        if head.startswith(_BINARY_SIGNATURES):
            raise ValueError(
                "PDF text extraction failed: the loader returned raw file bytes "
                "instead of text. This means the LlamaIndex PDF reader is not "
                "installed. Install it in the backend env:\n"
                "    uv add llama-index-readers-file\n"
                "    (or: pip install llama-index-readers-file)\n"
                "then re-ingest the document."
            )


def _load_with_llamaindex(file_path: str) -> List[Document]:
    reader = SimpleDirectoryReader(input_files=[file_path])
    raw_docs = reader.load_data()
    docs = [
        Document(
            text=clean_extracted_text(doc.text or ''),
            metadata=doc.metadata,
            id_=doc.id_,
        )
        for doc in raw_docs
    ]
    _assert_not_raw_binary(docs)
    return docs



def validate_text_documents(
    documents: List[Document],
    min_length: int = MIN_TEXT_LENGTH,
) -> None:

    total_text = " ".join((doc.text or '') for doc in documents).strip()
    if len(total_text) < min_length:
        raise ValueError(
            "Document contains insufficient text content. "
            "Only text-oriented documents are supported on the standard path. "
            "Scanned images, image-only PDFs, and non-text files are not allowed."
        )
