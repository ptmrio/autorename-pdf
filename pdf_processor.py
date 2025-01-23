import os
import sys
import logging
from typing import Dict, Tuple, Optional
from jellyfish import jaro_winkler_similarity
import datetime
import ocrmypdf
from ocrmypdf import exceptions as ocrmypdf_exceptions
from openai import OpenAI
from pgpt_python.client import PrivateGPTApi
from pdfminer.high_level import extract_text

import json
import dateparser
import re
import regex
import fitz  # PyMuPDF
import tempfile
import traceback
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import ctypes
import httpx



# Constants
PDF_EXTENSION = ".pdf"
UNKNOWN_VALUE = "Unknown"
DEFAULT_DATE = "00000000"
CONFIDENCE_THRESHOLD = 0.85

client = None

def set_env_vars(env_vars):
    for key, value in env_vars.items():
        os.environ[key] = value

def initialize_privateai_client():
    global client
    
    # initialize Defaults
    scheme = os.getenv('PRIVATEAI_SCHEME', 'http')
    host = os.getenv('PRIVATEAI_HOST',"localhost")
    port = os.getenv('PRIVATEAI_PORT',"8001")
    timeout = os.getenv('PRIVATEAI_TIMEOUT',720)
    base_url = f'%s://%s:%s' % (scheme, host, port)        
    # initialize client with default
    httpx_client = httpx.Client(timeout = timeout)
    client = PrivateGPTApi(base_url = base_url, 
                           httpx_client = httpx_client)
    logging.debug(f"Private API health {client.health.health()}")
    
    

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
            ocr_languages = os.getenv('OCR_LANGUAGES', 'deu,eng').split(',')
        
        try:
            ocrmypdf.ocr(
                pdf_path, 
                temp_path, 
                force_ocr=True,
                pages=f"{start_page}-{end_page}",
                language=ocr_languages,
                invalidate_digital_signatures=True,
                #output_type='pdfa-2'
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

def get_prompt_text():
    txt = "You will extract the company name, document date,"
    txt += " and document type from the following PDF text. "
    txt += "Due to the nature of OCR Text detection, the text will be very noisy and might "
    txt += "contain spelling and detection errors, handle those as good as possible." + "\n\n" 
    txt += "" + "\n\n" 
    txt += f"document_date: Find the most appropriate date (e.g. the invoice date) and assume the correct Date Format according to the language and location of the document. Return format must be: dd.mm.YYYY" + "\n\n" 
    txt += f"company_name: Find the name of the company that is the corresponding party of the document. My company name is: \"{os.getenv('MY_COMPANY_NAME')}\", avoid using my company name as company_name in the response. For the company_name you always strip the legal form (e.U., SARL, GmbH, AG, Lmt, Limited etc.)" + "\n\n" 
    txt += f"document_type: Find the best matching type of the document. Valid document types are: "
    txt += f"For incoming invoices (invoices my company receives) use the term '{os.getenv('PDF_INCOMING_INVOICE', 'ER')}' only, nothing more. "
    txt += f"For outgoing invoices (invoices my company sends) use the term '{os.getenv('PDF_OUTGOING_INVOICE', 'AR')}', nothing more. "
    txt += f"For all other document types, always find a short descriptive summary/subject in {os.getenv('OUTPUT_LANGUAGE', 'German')} language. " + "\n\n" 
    txt += "If a value is not found, leave it empty." + "\n\n"
    txt += "Output - adhere to the following JSON format: company_name, document_date, document_type. No additional text and no formatting."
    txt += "Strip everything from the response, except the json object output." 
    txt += os.getenv("PROMPT_EXTENSION", "")
    return txt.strip()

def get_open_ai_content(text: str):
    """call the public openai API using your API Key"""
    
    global client # dirty hack
    response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4"),
            messages=[
                {
                    "role": "system", 
                    "content": get_prompt_text()
                },
                {"role": "user", "content": f"Extract the information from the text:\n\n{text}"}
            ],
            response_format={ "type": "json_object" }
        )
    return response.choices[0].message.content


def get_private_ai_content(text: str):
    """call the private gpt API """
    
    global client # dirty hack
    response = client.contextual_completions.chat_completion(
            messages=[
                {
                    "role": "user", 
                    "content": get_prompt_text()
                },
                {"role": "user", "content": f"Extract the information from the text:\n\n{text}"},
            ],
        )
    return response.choices[0].message.content


def process_text_with_any_ai(text: str) -> Dict[str, str]:
    global client
    if client is None:
        raise ValueError("AI client not initialized. Call initialize_api_client first.")
    # some kind of adapter pattern is needed
    # determine by the classname what kind of api is to be called
    parsed_response = None
    response = None
    try:
        if isinstance(client, OpenAI):
            response = get_open_ai_content(text)
        elif isinstance(client, PrivateGPTApi):
            response = get_private_ai_content(text)
            model = os.getenv("PRIVATEAI_POST_PROCESSOR").split(',')[0]
            response = post_process_private_ai_response(response, model)
        else:                
            logging.error(f'Unknown API client: {type(client)}')
            raise Exception('Unknown API client: {type(client)}')


        logging.info(f'Extract Response: {response}')
        parsed_response = json.loads(response)
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
        logging.error(f"Error during API call: {e}")
    
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


def parse_ai_response(response: Dict[str, str]) -> Tuple[str, Optional[datetime.date], str]:
    """Parse the OpenAI response and extract relevant information."""
    company_name = response.get('company_name', UNKNOWN_VALUE)
    document_date = response.get('document_date', DEFAULT_DATE)
    document_type = response.get('document_type', UNKNOWN_VALUE)

    parsed_date = dateparser.parse(document_date, settings={'DATE_ORDER': 'DMY'})
    if parsed_date is None:
        parsed_date = dateparser.parse(DEFAULT_DATE, settings={'DATE_ORDER': 'DMY'})

    return company_name, parsed_date, document_type


def attempt_to_close_file(file_path: str) -> None:
    """Attempt to close the file if it's open (Windows-specific)."""
    if sys.platform == "win32":
        try:
            # Convert the file path to a wide character string
            file_path_wide = ctypes.c_wchar_p(file_path)
            # Attempt to close the file handle
            ctypes.windll.kernel32.CloseHandle(file_path_wide)
        except Exception as e:
            logging.warning(f"Failed to close file handle for {file_path}: {str(e)}")


def rename_invoice(pdf_path: str, company_name: str, document_date: Optional[datetime.date], document_type: str) -> None:
    """Rename the document based on extracted information."""
    if document_date:
        base_name = f'{document_date.strftime(os.getenv("OUTPUT_DATE_FORMAT", "%Y%m%d"))} {company_name} {document_type}'
    else:
        base_name = f'{company_name} {document_type}'

    new_name = f"{base_name}.pdf"
    new_name = new_name.replace(" ", "-")
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


def process_pdf(pdf_path: str, json_path: str) -> None:
    """Process a single PDF file."""
    logging.info("---")
    logging.info(f"Processing {pdf_path}")
    
    try:
        extracted_text = pdf_to_text(pdf_path)
        if not extracted_text:
            logging.warning(f"No text extracted from {pdf_path}. Skipping further processing.")
            return

        ai_response = process_text_with_any_ai(extracted_text)
        company_name, document_date, document_type = parse_ai_response(ai_response)
        company_name = harmonize_company_name(company_name, json_path)
        rename_invoice(pdf_path, company_name, document_date, document_type)
    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {str(e)}")
        logging.debug(traceback.format_exc())

        
def post_process_private_ai_response(text: str, model: str) -> str:
    """extract the json object string based on different models"""
    
    render = None
    
    if model == 'ollama':
        json_regex = r'\{(?:[^{}]|(?R))*\}'
        match = regex.search(json_regex, text, regex.DOTALL)
        if match:
            render = match.group(0)
    else:
        logging.error(f"failed to load PRIVATEAI_POST_PROCESSOR {model} ")
        raise Exception(f"failed to load PRIVATEAI_POST_PROCESSOR {model} ")
    
    return render

#@todo: externalize and fix
# def test_parser():
#     txt = """
#     ```
# {
#     "company_name": "Test GmbH",
#     "document_date": "18.11.2024",
#     "document_type": "INVOICE"
# }
# ```
#     """
#     model = os.getenv("PRIVATEAI_POST_PROCESSOR").split(',')[0]
#     raw = post_process_private_ai_response(txt, model)
    
#     if raw is None:
#         logging.error("post_process_private_ai_response parse error")
#     else:
#         logging.info(raw)