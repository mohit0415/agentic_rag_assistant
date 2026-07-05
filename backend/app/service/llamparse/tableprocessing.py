from typing import List, Optional
from llama_index.core.schema import TextNode
from llama_index.llms.azure_openai import AzureOpenAI
from openai import BadRequestError

from ...config.config import logger


class TableProcessor:
    def __init__(self, llm):
        self.llm = llm
    
    def process(self, table_text: str, metadata: dict = None) -> List[TextNode]:
        if not table_text or not table_text.strip():
            return []
        
        max_table_length = 5000 
        truncated_table = table_text[:max_table_length]
        if len(table_text) > max_table_length:
            truncated_table += "\n[... table truncated ...]"
            logger.warning(f"Table data truncated from {len(table_text)} to {max_table_length} characters")
        prompt = f"""You are a data analyst. Analyze the following table and provide a clear, factual summary.

Focus on:
- Key numerical values and figures
- Important trends or patterns
- Significant data points

Table data:
{truncated_table}

Provide a concise summary of the key information in this table."""
        
        try:
            response = self.llm.complete(prompt)
            summary = str(response).strip()
        except BadRequestError as e:
            error_message = str(e)
            if "content_filter" in error_message or "ResponsibleAIPolicyViolation" in error_message:
                logger.warning(f"Content filter triggered for table summary. Using fallback summary.")
                summary = self._create_fallback_summary(truncated_table)
            else:
                logger.error(f"Error generating table summary: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error generating table summary: {e}")
            summary = self._create_fallback_summary(truncated_table)
        
        node_metadata = metadata or {}
        node_metadata["content_type"] = "table_summary"
        node_metadata["original_table"] = table_text 
        node_metadata.setdefault("modality", "table")
        node_metadata.setdefault("level", "node")

        node = TextNode(
            text=summary,
            metadata=node_metadata,
        )
        
        return [node]
    
    def _create_fallback_summary(self, table_text: str) -> str:
        lines = table_text.split('\n')
        row_count = sum(1 for line in lines if line.strip() and '|' in line)
        header = ""
        for line in lines[:3]:
            if '|' in line and not all(c in '|-: ' for c in line.strip()):
                header = line.strip()
                break
        
        summary = f"Table containing {row_count} rows"
        if header:
            summary += f" with columns: {header[:200]}"
        
        summary += ". Table data available in original format."
        return summary

