"""Image processing module for generating text captions using ImageNode (same as demo-2)."""

import shutil
from typing import List, Optional, Any
from pathlib import Path
from llama_index.core.schema import ImageNode
from llama_index.llms.azure_openai import AzureOpenAI

from .image_captioning import generate_caption
from ...config.config import logger

IMAGES_STORAGE_DIR = Path("stored_images")


class ImageProcessor:
    def __init__(self, llm: Optional[AzureOpenAI] = None, multi_modal_llm: Optional[Any] = None):
        self.llm = llm
        
        IMAGES_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Images will be stored in: {IMAGES_STORAGE_DIR.absolute()}")
    
    def process_from_path(self, image_path: str, metadata: dict = None) -> List[ImageNode]:

        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        api_key = getattr(self.llm, "api_key", None)
        caption = generate_caption(image_path, api_key=api_key)
        logger.debug(f"Generated caption: {caption[:100]}...")
        
        source_path = Path(image_path)
        source_name = metadata.get("source", "unknown") if metadata else "unknown"
        safe_source_name = Path(source_name).stem.replace(" ", "_")
        page = metadata.get("page", 0) if metadata else 0
        image_index = metadata.get("image_index", 0) if metadata else 0
        
        permanent_filename = f"{safe_source_name}_page{page}_img{image_index}{source_path.suffix}"
        permanent_path = IMAGES_STORAGE_DIR / permanent_filename
        
        shutil.copy2(source_path, permanent_path)
        logger.info(f"Stored image permanently at: {permanent_path}")
        permanent_path_str = str(permanent_path)
        
        node_metadata = metadata or {}
        node_metadata["content_type"] = "image_caption"
        node_metadata["image_path"] = permanent_path_str  
        node_metadata.setdefault("modality", "diagram")
        node_metadata.setdefault("level", "node")
        image_node = ImageNode(
            text=caption,  
            image_path=permanent_path_str, 
            metadata=node_metadata,
        )
        
        return [image_node]

