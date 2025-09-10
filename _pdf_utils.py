"""
PDF processing utilities for text extraction and OCR.
This module handles PDF text extraction using OCR and direct methods.
"""

import os
import logging
import fitz  # PyMuPDF
import tempfile
import ocrmypdf

def pdf_to_text(pdf_path: str, start_page: int = 1, end_page: int = 3) -> str:
    """Process PDF: try OCR first, fallback to direct text extraction."""
    all_text = ""
    
    try:
        # Step 1: Try OCR with safety limits
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_path = temp_file.name
            ocr_languages = os.getenv('OCR_LANGUAGES', 'deu,eng').split(',')
        
        try:
            ocrmypdf.ocr(
                pdf_path, 
                temp_path, 
                force_ocr=True,
                pages=f"{start_page}-{end_page}",
                language=ocr_languages,
                invalidate_digital_signatures=True,
                dpi=150,  # Limit DPI
                optimize=1,
                oversample=150
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
 
    logging.info(f"Extracted text (first 500 characters): {all_text[:500]}...")
    
    if not all_text.strip():
        logging.warning(f"No text extracted from {pdf_path}")
    
    return all_text.strip()
