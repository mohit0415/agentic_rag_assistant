import logging
import os
from typing import Any, List, Optional

from llama_index.core.tools import BaseTool

try:
    from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
except ImportError:
    logging.warning(
        "llama-index-tools-mcp not found. Install it with: "
        "pip install llama-index-tools-mcp"
    )
    BasicMCPClient = Any
    McpToolSpec = Any

from ..config.config import logger

PUBMED_TOOLS = [
    "pubmed_search_articles",
    "pubmed_europepmc_search",
    "pubmed_fetch_articles",
    "pubmed_fetch_fulltext",
    "pubmed_format_citations",
    "pubmed_find_related",
    "pubmed_spell_check",
    "pubmed_lookup_mesh",
    "pubmed_lookup_citation",
    "pubmed_convert_ids",
]


class PubMedMCPService:
    def __init__(self) -> None:
        self.url = os.getenv("PUBMED_MCP_URL", "https://pubmed.caseyjhand.com/mcp")
        self.token = os.getenv("PUBMED_MCP_TOKEN")
        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def load_tools(self, allowed_tools: Optional[List[str]] = None) -> List[BaseTool]:
        logger.info(f"Connecting to PubMed MCP Server at {self.url}...")

        try:
            client = BasicMCPClient(
                command_or_url=self.url,
            )
            tool_spec = McpToolSpec(client=client)

            tools = await tool_spec.to_tool_list_async()
            if allowed_tools:
                filtered_tools = [t for t in tools if t.metadata.name in allowed_tools]
                logger.info(
                    f"Filtered to {len(filtered_tools)} tools from {len(tools)} available"
                )
                logger.info(
                    f"Successfully loaded {len(filtered_tools)} tools: "
                    f"{[t.metadata.name for t in filtered_tools]}"
                )
                return filtered_tools

            logger.info(
                f"Successfully loaded {len(tools)} tools: "
                f"{[t.metadata.name for t in tools]}"
            )
            return tools

        except Exception as e:
            logger.error(f"Failed to load PubMed MCP tools: {str(e)}")
            raise ConnectionError(f"Could not connect to PubMed MCP Server: {e}")



