import os
import base64
from pathlib import Path
from typing import Optional

from openai import AzureOpenAI as AzureOpenAIClient
from openai import OpenAI
from llama_index.llms.azure_openai import AzureOpenAI
from dotenv import load_dotenv

from ...config.config import load_config, logger


def generate_caption(image_path: str, prompt: Optional[str] = None, api_key: Optional[str] = None) -> str:

    logger.info(f"Generating caption for image: {image_path}")
    load_dotenv()
    
    if prompt is None:
        prompt = (
            "Describe this image so it can be found and quoted by a search "
            "system without seeing the image. Include: (1) what kind of image "
            "it is (bar/line/pie chart, diagram, photo, table); (2) its title "
            "and axis/legend labels verbatim; (3) EVERY data point, label and "
            "value you can read — e.g. each bar/slice/point with its exact "
            "number or percentage; (4) for diagrams, every component name and "
            "the connections between them, in order. Be exhaustive about "
            "text and numbers, concise about style."
        )
    
    logger.debug(f"Reading and encoding image: {image_path}")
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()
        image_data = base64.b64encode(image_bytes).decode("utf-8")
    
    image_size_mb = len(image_bytes) / (1024 * 1024)
    logger.debug(f"Image size: {image_size_mb:.2f} MB, base64 encoded length: {len(image_data)} characters")
    
    ext = Path(image_path).suffix.lower()
    mime_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    mime_type = mime_type_map.get(ext, "image/png")
    logger.debug(f"Detected MIME type: {mime_type} for extension: {ext}")
    
    config = load_config()

    if config.get('use_gemini'):
        gemini_base = config.get('gemini_openai_base')
        if not gemini_base:
            raise ValueError('Image Captioning Model URL Not Present')
        if not api_key:
            raise EnvironmentError(
                "Gemini API key required for image captioning (carried inside the verified JWT)."
            )
        gemini_key = api_key or config.get('gemini_api_key')
        if not gemini_key:
            raise EnvironmentError(
                "Gemini API key required for image captioning "
                "(set GEMINI_API_KEY or pass it via the request LLM)."
            )
        client = OpenAI(api_key=gemini_key, base_url=gemini_base)
        llm_deployment = config.get('gemini_llm_model', 'gemini-2.5-flash')
    else:
        azure_api_key = api_key or config.get('azure_api_key')
        endpoint = config.get('azure_endpoint')
        api_version = config.get('api_version')
        azure_llm_deployment = config.get('azure_llm_deployment')

        if not all([azure_api_key, endpoint, azure_llm_deployment]):
            logger.error("Missing required environment variables for Azure OpenAI")
            raise EnvironmentError(
                "Missing required environment variables for Azure OpenAI"
            )

        logger.debug(f"Initializing Azure OpenAI client: endpoint={endpoint}, deployment={azure_llm_deployment}")
        client = AzureOpenAIClient(
            api_key=azure_api_key,
            api_version=api_version,
            azure_endpoint=endpoint,
        )
        llm_deployment = azure_llm_deployment
    
    logger.info(f"Calling Azure OpenAI vision API for caption generation (deployment: {llm_deployment})")
    response = client.chat.completions.create(
        model=llm_deployment,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}"
                        }
                    }
                ]
            }
        ],
        max_tokens=1500,
    )
    
    caption = response.choices[0].message.content.strip()
    logger.info(f"Caption generated successfully (length: {len(caption)} characters): {caption[:100]}...")
    
    return caption

