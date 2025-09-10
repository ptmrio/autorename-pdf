"""
Document processing utilities for company name harmonization and file operations.
This module handles company name harmonization and document renaming operations.
"""

import os
import logging
import json
import datetime
import dateparser
from typing import Dict, Tuple, Optional
from jellyfish import jaro_winkler_similarity
from _utils import UNKNOWN_VALUE, DEFAULT_DATE, attempt_to_close_file
from _config_loader import load_company_names

# Constants
CONFIDENCE_THRESHOLD = 0.85

def harmonize_company_name(company_name: str, yaml_path: str) -> str:
    """Harmonize company name based on predefined mappings."""
    company_name = company_name.strip()
    if not os.path.exists(yaml_path):
        logging.warning(f'{yaml_path} not found, using original name: {company_name}')
        return company_name

    harmonized_names = load_company_names(yaml_path)
    if not harmonized_names:
        logging.warning(f'No company names loaded from {yaml_path}, using original name: {company_name}')
        return company_name

    best_match = max(
        ((harmonized_name, max(jaro_winkler_similarity(company_name.lower(), synonym.lower()) for synonym in synonyms))
         for harmonized_name, synonyms in harmonized_names.items()),
        key=lambda x: x[1]
    )

    if best_match[1] > CONFIDENCE_THRESHOLD:
        logging.info(f'Using harmonized company name: {best_match[0]}')
        return best_match[0]

    logging.info(f'No harmonized company name found, using original name: {company_name}')
    return company_name

def parse_ai_response(response: Dict[str, str]) -> Tuple[str, Optional[datetime.date], str]:
    """Parse the AI response and extract relevant information."""
    company_name = response.get('company_name', UNKNOWN_VALUE)
    document_date = response.get('document_date', DEFAULT_DATE)
    document_type = response.get('document_type', UNKNOWN_VALUE)

    parsed_date = dateparser.parse(document_date, settings={'DATE_ORDER': 'DMY'})
    if parsed_date is None:
        parsed_date = dateparser.parse(DEFAULT_DATE, settings={'DATE_ORDER': 'DMY'})

    return company_name, parsed_date, document_type

def rename_invoice(pdf_path: str, company_name: str, document_date: Optional[datetime.date], document_type: str) -> None:
    """Rename the document based on extracted information."""
    if document_date:
        base_name = f'{document_date.strftime(os.getenv("OUTPUT_DATE_FORMAT", "%Y%m%d"))} {company_name} {document_type}'
    else:
        base_name = f'{company_name} {document_type}'

    new_name = f"{base_name}.pdf"
    new_path = os.path.join(os.path.dirname(pdf_path), new_name)

    if pdf_path == new_path:
        logging.info(f'File "{new_name}" is already correctly named.')
        return

    counter = 0
    while os.path.exists(new_path):
        counter += 1
        new_name = f'{base_name}_({counter}).pdf'
        new_path = os.path.join(os.path.dirname(pdf_path), new_name)

    try:
        # Attempt to close the file before renaming
        attempt_to_close_file(pdf_path)
        
        os.rename(pdf_path, new_path)
        logging.info(f'Document renamed to: {new_name}')
    except Exception as e:
        logging.error(f'Error renaming {pdf_path}: {str(e)}')
