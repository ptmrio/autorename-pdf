"""
PDF processing utilities for text extraction and OCR.
This module handles PDF text extraction using OCR and direct methods.
"""

import os
import logging
import fitz  # PyMuPDF
import tempfile
import ocrmypdf
from PIL import Image

def pdf_to_text(pdf_path: str, start_page: int = 1, end_page: int = 3) -> str:
    """Process PDF: try OCR first, fallback to direct text extraction."""
    all_text = ""
    
    # Store original PIL limit for safe restoration
    original_pil_limit = Image.MAX_IMAGE_PIXELS
    
    try:
        # Step 1: Try OCR with safety limits
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_path = temp_file.name
            ocr_languages = os.getenv('OCR_LANGUAGES', 'deu,eng').split(',')
        
        try:
            # Temporarily increase PIL limit to handle large images safely
            # 200MP is much higher than default (89.5MP) but still reasonable
            Image.MAX_IMAGE_PIXELS = 200000000
            
            ocrmypdf.ocr(
                pdf_path, 
                temp_path, 
                skip_text=True,                           # Changed from force_ocr=True
                pages=f"{start_page}-{end_page}",
                language=ocr_languages,
                invalidate_digital_signatures=True,
                optimize=0,                               # Disable image optimization for speed
                output_type='pdf',                        # Skip PDF/A conversion
                fast_web_view=False,                      # Disable linearization  
                oversample=150,                           # Keep your current setting
                tesseract_timeout=60,                     # Reduce timeout for speed
                tesseract_downsample_large_images=True,   # Auto-downsample large images
                max_image_mpixels=50,                     # Skip images >50MP
                jobs=4                                    # Parallel processing
            )
            
            # Extract text from OCR'd PDF
            doc = fitz.open(temp_path)
            for page_num in range(start_page - 1, min(end_page, len(doc))):
                page = doc[page_num]
                page_text = page.get_text()
                all_text += f"Page {page_num + 1}:\n{page_text}\n\n"
            doc.close()
            os.unlink(temp_path)
            
        except Exception as ocr_error:
            logging.warning(f"OCR failed for {pdf_path}: {ocr_error}")
            logging.info("Falling back to direct text extraction...")
            
            # Fallback: Direct text extraction without OCR
            doc = fitz.open(pdf_path)
            for page_num in range(start_page - 1, min(end_page, len(doc))):
                page = doc[page_num]
                page_text = page.get_text()
                all_text += f"Page {page_num + 1}:\n{page_text}\n\n"
            doc.close()

    except Exception as e:
        logging.error(f"Error processing PDF {pdf_path}: {str(e)}")
    finally:
        # Always restore original PIL limit for security
        Image.MAX_IMAGE_PIXELS = original_pil_limit
 
    logging.info(f"Extracted text (first 500 characters): {all_text[:500]}...")
    
    if not all_text.strip():
        logging.warning(f"No text extracted from {pdf_path}")
    
    return all_text.strip()