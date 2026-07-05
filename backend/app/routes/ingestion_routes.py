import os
import re
import logging
import hashlib
import tempfile
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request, Response
from pydantic import BaseModel, Field, field_validator
from llama_index.core import SimpleDirectoryReader
from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter
from ..service.documents import Document_Process, clean_extracted_text
from ..config.config import logger
from ..auth.security import get_current_claims
from ..core.limiter import limiter, RATE_LIMIT_UPLOAD
from ..service.metadata import DocumentMetadataExtractor
from ..service.indexing import Indexing
from ..service.vectordb import VectorDB,NodeInsertionError
from ..service.chunking import Chunking_Strategy
from ..service.llms import build_models_from_claims, get_active_embed_model_name
from ..service.multimodal import MultiModal
from llama_index.core.schema import Document


router = APIRouter()


def get_app_state():
    """Lazy import of app_state to avoid circular import"""
    from ..app import app_state
    return app_state


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_QUERY_LENGTH = 2000
MIN_SIMILARITY_TOP_K = 1
MAX_SIMILARITY_TOP_K = 20

ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.md', '.docx'}



class UploadResponse(BaseModel):
    message: str
    documents_indexed: int
    llama_parse_usage : bool
    total_nodes_parse : int
    table_nodes_parse : int
    image_nodes_parse : int
    parsed_with : str


def sanitize_filename(filename: str) -> str:
    if not filename:
        raise ValueError("Filename cannot be empty")
  
    filename = os.path.basename(filename)

    filename = filename.replace('/', '_').replace('\\', '_')
    
    filename = re.sub(r'[^\w\s.-]', '', filename)
    
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    
    return filename



@router.post("/upload", response_model=UploadResponse)
@limiter.limit(RATE_LIMIT_UPLOAD)
async def upload_document(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    claims: Dict[str, Any] = Depends(get_current_claims),
):
    file_path = None
    try:
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Filename is required"
            )
        
        safe_filename = sanitize_filename(file.filename)
        file_ext = os.path.splitext(safe_filename)[1].lower()
        
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024):.1f}MB"
            )

        # ---- Duplicate-upload prevention (content-based) ----
        # SHA-256 of the raw bytes identifies the *content*, not the filename:
        # the same doc re-uploaded under a different name is still caught, while
        # a genuinely modified version (different bytes) is allowed through.
        # Checked BEFORE any parsing so duplicates cost no LlamaParse/LLM calls.
        file_hash = hashlib.sha256(content).hexdigest()
        if Indexing.file_hash_exists(file_hash):
            raise HTTPException(
                status_code=409,
                detail=f"'{safe_filename}' is already indexed (identical content was uploaded before). Duplicate uploads are skipped to keep retrieval quality high."
            )


        documents_load = Document_Process(data=content,file_ext=file_ext)


        # Step 1: LlamaIndex load_docs — the cheap, first-choice path for every
        # supported type (.pdf/.docx/.txt/.md). Tables/images are no longer
        # rejected here; the routing decision happens in step 2.
        try:
            documents,file_path = documents_load.process_docs()
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        logger.info(f"File uploaded: {safe_filename} ({len(content)} bytes)")
        

        logger.info(f"Loaded {len(documents)} document(s) from {safe_filename}")


        # Resolve the per-user models from the verified JWT (Gemini mode) or the
        # env-configured Azure models.
        llm, embed_model = build_models_from_claims(claims)

        # ---- Embedding-model compatibility gate (BEFORE any parsing cost) ----
        # Every chunk is stamped with the embed model that produced its vector
        # (see the metadata loop below). If the table already holds chunks from
        # a DIFFERENT embedding model (e.g. after flipping USE_GEMINI), refuse
        # the upload: mixing vector spaces in one table silently breaks
        # retrieval for everything.
        active_embed_name = get_active_embed_model_name()
        compatible, mismatch_msg = Indexing.check_embed_model_compatibility(active_embed_name)
        if not compatible:
            raise HTTPException(status_code=409, detail=mismatch_msg)



        chunk_obj = Chunking_Strategy(embed_model=embed_model)



        # Step 2: cost-aware routing. The file is scanned for tables/images; only
        # when present is it re-parsed with LlamaParse (markdown + image captions
        # + table summaries). Plain-text documents keep the LlamaIndex result, so
        # the LlamaParse cost is paid only when actually required. The LlamaParse
        # key is read from the verified JWT claims.

        doc_service = MultiModal(file_path=file_path,file_ext=file_ext,standard_documents=documents,llamaparse_api_key = claims.get('llamaparse_api_key'),llm=llm,embed_model=embed_model,original_filename = safe_filename)
        use_Llama_Parse = doc_service.requires_multimodal_parsing()

        tables_count = 0
        images_count = 0
        total_nodes = 0

        if use_Llama_Parse:
            full_text = doc_service.orchestrate_document_parsing()

            result = doc_service.process_docs_find(full_text=full_text,embed_model=embed_model,llm=llm)
            nodes= result.get('all_nodes',[])
            tables_count = result.get('table_nodes',0)
            images_count = result.get('image_nodes',0)
            total_nodes = result.get('total_nodes',0) 
        else:
            for doc in documents:
                metadatas = DocumentMetadataExtractor(doc=doc,llm=llm,file_path=file_path,original_filename=safe_filename)
                doc.metadata = metadatas.enrich().metadata.copy()
            documents_refine = [
                Document(
                    text=clean_extracted_text(doc.text or ''),
                    metadata=doc.metadata,
                    id_=doc.id_,
                )
            for doc in documents]
            nodes = chunk_obj.extract_nodes_from_docs(documents=documents_refine)

        # Stamp every node (both LlamaIndex and LlamaParse paths) with the file
        # content hash so future uploads of the same bytes are detected, and
        # exclude it from embedding/LLM text so it never pollutes retrieval.
        for node in nodes:
            node.metadata['file_hash'] = file_hash
            # Stamp WHICH embedding model produced this chunk's vector, so a
            # later provider/model switch is detected at query time instead of
            # silently comparing vectors from different spaces. Excluded from
            # embed/LLM text (like file_hash) so it never pollutes retrieval.
            node.metadata['embed_model'] = active_embed_name
            for key in ('file_hash', 'embed_model'):
                if key not in node.excluded_embed_metadata_keys:
                    node.excluded_embed_metadata_keys.append(key)
                if key not in node.excluded_llm_metadata_keys:
                    node.excluded_llm_metadata_keys.append(key)

        index_obj = Indexing(embed_model=embed_model)
        index = index_obj.load_or_create_index()
        # The index instance is cached process-wide (see indexing.py's module
        # level `_index`). In Gemini mode each request can carry a different
        # user's embed model/key, so without this override insert_nodes() below
        # would embed new nodes with whichever embed_model built the cached
        # index first, not this request's. Mirrors the same override already
        # applied in query_routes.py before retrieval.
        index._embed_model = embed_model
        # ------------------------------------------------
        try:
            vectorStoreIndex =VectorDB(current_index=index,nodes=nodes)

            ingestion_verify_dict = vectorStoreIndex.insert_nodes_index()

            if use_Llama_Parse:
                llama_parse = "LlamaParse"
            else:
                llama_parse = "LlamaIndex"

        except NodeInsertionError as nie:
            # Log full details for operators, but return a concise, non-sensitive message to clients
            logger.error("Indexing error while uploading document %s: %s", safe_filename, nie, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Internal indexing error: {str(nie)}"
            )
        
        
        return UploadResponse(
                message=ingestion_verify_dict.get('message','Indexed'),
                documents_indexed=len(documents),
                llama_parse_usage=use_Llama_Parse,
                table_nodes_parse=tables_count,
                image_nodes_parse=images_count,
                total_nodes_parse=total_nodes,
                parsed_with=llama_parse
            )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except ConnectionError as e:
        # e.g. Indexing.load_or_create_index() -> "DB connection failed: ..."
        logger.error(f"Connection error while uploading document: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Service unavailable: {str(e)}"
        )
    except Exception as e:
        # Surface the ORIGINAL error (type + message) to the client instead of
        # a generic "Failed to process document", so upload failures are
        # diagnosable from the UI without reading server logs.
        logger.error(f"Error uploading document: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {type(e).__name__}: {str(e)}"
        )
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {file_path}: {e}")