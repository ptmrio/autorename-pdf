import os
import sys
import logging
from typing import Dict, Tuple, Optional
from jellyfish import jaro_winkler_similarity
import datetime
import ocrmypdf
from ocrmypdf import exceptions as ocrmypdf_exceptions
from openai import OpenAI
import json
import dateparser
import re
import fitz  # PyMuPDF
import tempfile
import traceback
from pydantic import BaseModel, Field

# Constants
PDF_EXTENSION = ".pdf"
UNKNOWN_VALUE = "Unknown"
DEFAULT_DATE = "00000000"
CONFIDENCE_THRESHOLD = 0.85

client = None

if getattr(sys, 'frozen', False):
    current_directory = os.path.dirname(sys.executable)  # Path to the folder containing the .exe
else:
    current_directory = os.path.dirname(os.path.abspath(__file__))  # Path to the script file

def initialize_openai_client(api_key):
    global client
    client = OpenAI(api_key=api_key)

class DocumentResponse(BaseModel):
    company_name: str = Field(..., description="Name of the company in the document")
    document_date: str = Field(..., description="Date of the document in format dd.mm.yyyy")
    document_type: str = Field(..., description="Type of the document (ER, AR, etc.)")


def is_valid_filename(filename: str) -> bool:
    forbidden_chars = r'[<>:"/\\|?*]'
    
    if re.search(forbidden_chars, filename):
        return False
    
    if not filename or filename.isspace():
        return False
    
    if len(filename) > 255:
        return False
    
    return True


def pdf_to_text(pdf_path: str, start_page: int = 1, end_page: int = 3) -> str:
    """Process PDF: always run OCR first, then extract text using PyMuPDF."""
    all_text = ""
    
    try:
        # Step 1: Always run OCR
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_path = temp_file.name
        
        try:
            ocrmypdf.ocr(
                pdf_path, 
                temp_path, 
                force_ocr=True,
                pages=f"{start_page}-{end_page}",
                language=['eng', 'deu'],
                invalidate_digital_signatures=True
            )
        except ocrmypdf_exceptions.PriorOcrFoundError:
            logging.warning(f"Prior OCR found in {pdf_path}. Skipping OCR step.")
            temp_path = pdf_path
        
        # Step 2: Extract text using PyMuPDF (fitz)
        doc = fitz.open(temp_path)
        for page_num in range(start_page - 1, min(end_page, len(doc))):
            page = doc[page_num]
            page_text = page.get_text()
            all_text += f"Page {page_num + 1}:\n{page_text}\n\n"
        doc.close()
        
        # Clean up temporary file
        os.unlink(temp_path)

    except Exception as e:
        logging.error(f"Error processing PDF {pdf_path}: {str(e)}")

    logging.info(f"Extracted text (first 500 characters): {all_text[:500]}...")
    
    if not all_text.strip():
        logging.warning(f"No text extracted from {pdf_path}")
    
    return all_text.strip()


def process_text_with_openai(text: str) -> Dict[str, str]:
    """Process the extracted text with OpenAI API."""
    global client
    if client is None:
        raise ValueError("OpenAI client not initialized. Call initialize_openai_client first.")

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4"),
            messages=[
                {
                    "role": "system", 
                    "content": "You will extract the company name, document date, and document type from the following PDF text. " +
                        "Adhere to the following JSON format: company_name, document_date, document_type. " +
                        "No additional text and no formatting. Only the JSON object." +
                        "Due to the nature of OCR Text detection, the text will be very noisy and might contain spelling errors, handle those as good as possible." +
                        "For the company_name you always strip the legal form (e.U., SARL, GmbH, AG, Lmt, Limited etc.)" +
                        "If the text language is German, assume a European date format (dd.mm.YYYY or dd/mm/YYYY or reverse) in the provided text. Return format: dd.mm.YYYY" +
                        "Valid document types are: For incoming invoices (invoices my company receives) use the term 'ER' only, nothing more. For outgoing invoices (invoices my company sends) use the term 'AR', nothing more." +
                        "For all other documents, find a short descriptive summary/subject in german language." +
                        "If a value is not found, leave it empty." +
                        f"My company name is: \"{os.getenv('MY_COMPANY_NAME')}\", avoid using my company name as company_name in the response."
                 },
                {"role": "user", "content": f"Extract the information from the text:\n\n{text}"}
            ],
            response_format={ "type": "json_object" }
        )
        
        content = response.choices[0].message.content
        parsed_response = json.loads(content)
        logging.info(f'API Extract Response: {parsed_response}')

        company_name = parsed_response.get('company_name', UNKNOWN_VALUE)
        document_date = parsed_response.get('document_date', DEFAULT_DATE)
        document_type = parsed_response.get('document_type', UNKNOWN_VALUE)

        if not is_valid_filename(company_name):
            company_name = UNKNOWN_VALUE
        if not is_valid_filename(document_type):
            document_type = UNKNOWN_VALUE
        if not is_valid_filename(document_date):
            document_date = DEFAULT_DATE

        return {"company_name": company_name, "document_date": document_date, "document_type": document_type}

    except Exception as e:
        logging.error(f"Error during OpenAI API call: {e}")
    
    return {"company_name": UNKNOWN_VALUE, "document_date": DEFAULT_DATE, "document_type": UNKNOWN_VALUE}


def harmonize_company_name(company_name: str, json_path: str) -> str:
    """Harmonize company name based on predefined mappings."""
    company_name = company_name.strip()
    if not os.path.exists(json_path):
        logging.warning(f'{json_path} not found, using original name: {company_name}')
        return company_name

    with open(json_path, "r", encoding='utf-8') as file:
        harmonized_names = json.load(file)

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

def parse_openai_response(response: Dict[str, str]) -> Tuple[str, Optional[datetime.date], str]:
    """Parse the OpenAI response and extract relevant information."""
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
        base_name = f'{document_date.strftime("%Y%m%d")} {company_name} {document_type}'
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
        new_name = f'{base_name} ({counter}).pdf'
        new_path = os.path.join(os.path.dirname(pdf_path), new_name)

    try:
        os.rename(pdf_path, new_path)
        logging.info(f'Document renamed to: {new_name}')
    except Exception as e:
        logging.error(f'Error renaming {pdf_path}: {str(e)}')

def process_pdf(pdf_path: str, json_path: str) -> None:
    """Process a single PDF file."""
    logging.info("---")
    logging.info(f"Processing {pdf_path}")
    try:
        extracted_text = pdf_to_text(pdf_path)
        if not extracted_text:
            logging.warning(f"No text extracted from {pdf_path}. Skipping further processing.")
            return

        openai_response = process_text_with_openai(extracted_text)
        company_name, document_date, document_type = parse_openai_response(openai_response)
        company_name = harmonize_company_name(company_name, json_path)
        rename_invoice(pdf_path, company_name, document_date, document_type)
    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {str(e)}")
        logging.debug(traceback.format_exc())
