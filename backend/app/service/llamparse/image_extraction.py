from pathlib import Path
from typing import List, Dict, Any
import fitz  # PyMuPDF

from ...config.config import logger


def extract_images_from_pdf(pdf_path: str, output_dir: str) -> List[Dict[str, Any]]:
    logger.info(f"Opening PDF file: {pdf_path}")
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    logger.info(f"PDF opened successfully, total pages: {total_pages}")
    
    results = []
    try:
        for page_index in range(total_pages):
            logger.debug(f"Processing page {page_index + 1}/{total_pages}")
            page = doc.load_page(page_index)
            images = page.get_images(full=True)
            
            if not images:
                logger.debug(f"No images found on page {page_index + 1}")
                continue
            
            logger.info(f"Found {len(images)} image(s) on page {page_index + 1}")
            
            for img_index, img in enumerate(images):
                xref = img[0]
                logger.debug(f"Extracting image {img_index + 1} from page {page_index + 1} (xref: {xref})")
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                ext = base_image.get("ext", "png")
                out_path = Path(output_dir) / f"extracted_image_page{page_index}_img{img_index}.{ext}"
                
                with open(out_path, "wb") as f:
                    f.write(image_bytes)
                
                image_size = len(image_bytes)
                logger.debug(f"Saved image to {out_path} (size: {image_size} bytes)")
                
                results.append({
                    "path": str(out_path),
                    "page": page_index,
                    "image_index": img_index,
                })
        
        if not results:
            logger.error("No images found in the PDF")
            raise RuntimeError("No images found in the PDF")
        
        logger.info(f"Image extraction completed: {len(results)} images extracted from {total_pages} pages")
        return results
    finally:
        doc.close()
        logger.debug("PDF document closed")





