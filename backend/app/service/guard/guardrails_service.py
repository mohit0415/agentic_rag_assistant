from llama_index.core import Document, Settings
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from typing import List, Dict, Any, Optional
import os
from ..guard.validatior_guard import GuardrailsValidator, get_guardrails_validator



class GuardrailsService:
    
    def __init__(
        self,
        documents: Optional[List[Document]] = None,
        validator: Optional[GuardrailsValidator] = None,
        retrieval_service: Optional[Any] = None,
    ):
        self.documents = documents if documents is not None else []
        self.validator = validator if validator is not None else get_guardrails_validator()
        self.retrieval_service = retrieval_service
    
    
    def safe_query(
        self, 
        query_text: str, 
        enable_pii_check: bool = True,
        enable_input_validation: bool = True
    ) -> Dict[str, Any]:
        validation_results = {
            "input_validated": False,
            "input_validation_error": None,
            "pii_detected": False,
            "pii_summaries": []
        }
        
        if enable_input_validation:
            is_valid, error_message = self.validator.validate_input(query_text)
            if not is_valid:
                validation_results["input_validation_error"] = error_message
                return {
                    "query": query_text,
                    "answer": f"Query blocked: Input validation failed. {error_message}",
                    "retrieved_nodes": [],
                    "validation_results": validation_results
                }
            validation_results["input_validated"] = True
        
        if self.retrieval_service is None or not self.documents:
            return {
                "query": query_text,
                "answer": "No documents available in the database. Please upload documents first using POST /api/ingestion/upload",
                "retrieved_nodes": [],
                "validation_results": validation_results
            }
        
        response_text = self.retrieval_service.query(query_text)
        retrieved_nodes = self.retrieval_service.retrieve(query_text)
        
        is_valid, sanitized_text, pii_summaries = self.validator.validate_output(
            response_text,
            check_pii=enable_pii_check
        )

        if pii_summaries:
            validation_results["pii_detected"] = True
            validation_results["pii_summaries"] = pii_summaries
        
        return {
            "query": query_text,
            "answer": sanitized_text,
            "retrieved_nodes": retrieved_nodes,
            "validation_results": validation_results
        }
