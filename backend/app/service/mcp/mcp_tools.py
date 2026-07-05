import logging
import os
from typing import List

from llama_index.core.tools import BaseTool
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec

from ...config.config import logger


class PubMedService:
    def __init__(self) -> None:
        self.url = os.getenv(
            "PUB_MED_MCP_URL",
            "https://pubmed.mcp.claude.com/mcp",
        )

    async def load_tools(
        self,
        allowed_tools: List[str] | None = None,
    ) -> List[BaseTool]:

        logger.info(f"Connecting to MCP server: {self.url}")

        try:
            client = BasicMCPClient(
                command_or_url=self.url,
                timeout=60,
            )

            tool_spec = McpToolSpec(
                client=client,
                allowed_tools=allowed_tools,
            )

            tools = await tool_spec.to_tool_list_async()

            logger.info(
                "Successfully loaded %d MCP tools.",
                len(tools),
            )

            logger.info(
                "Tools: %s",
                [tool.metadata.name for tool in tools],
            )

            return tools

        except Exception:
            logger.exception("Unable to connect to PubMed MCP server.")
            raise