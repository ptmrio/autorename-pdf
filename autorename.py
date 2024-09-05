import os
import sys
import logging
from typing import Dict, Tuple, Optional
from jellyfish import jaro_winkler_similarity
from dotenv import load_dotenv
from pdf2image import convert_from_path
import datetime
import pytesseract
from openai import OpenAI
import json
import dateparser
import re
from PIL import Image
import cv2
import numpy as np
from pydantic import BaseModel, Field

# Constants
PDF_EXTENSION = ".pdf"
UNKNOWN_VALUE = "Unknown"
DEFAULT_DATE = "00000000"
CONFIDENCE_THRESHOLD = 0.85

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if getattr(sys, 'frozen', False):
    current_directory = os.path.dirname(sys.executable)  # Path to the folder containing the .exe
else:
    current_directory = os.path.dirname(os.path.abspath(__file__))  # Path to the script file

# Define the path to the .env file
env_path = os.path.join(current_directory, '.env')

# Load environment variables from the .env file
load_dotenv(env_path)

openai_model = os.getenv("OPENAI_MODEL")
my_company_name = os.getenv("MY_COMPANY_NAME")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

def preprocess_image(image):
    # Convert to grayscale
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    # Apply thresholding to preprocess the image
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    # Apply dilation to remove noise
    kernel = np.ones((1, 1), np.uint8)
    gray = cv2.dilate(gray, kernel, iterations=1)
    return Image.fromarray(gray)

def pdf_to_text(pdf_path: str, start_page: int = 1, end_page: int = 1) -> str:
    """Convert a range of pages from a PDF to text using OCR with preprocessing."""
    try:
        images = convert_from_path(pdf_path, first_page=start_page, last_page=end_page)
        text = ""
        for image in images:
            # Preprocess the image
            processed_image = preprocess_image(image)
            # Perform OCR with specific configuration
            page_text = pytesseract.image_to_string(
                processed_image, 
                config='--psm 6 --oem 3 -c preserve_interword_spaces=1'
            )
            text += page_text + "\n\n"
        return text.strip()
    except Exception as e:
        logging.error(f"Error converting PDF to text: {e}")
        return ""

def get_openai_response(pdf_path: str) -> Dict[str, str]:
    """Get structured information from OpenAI API, potentially using multiple pages."""
    text = pdf_to_text(pdf_path, start_page=1, end_page=1)
    response = process_text_with_openai(text)
    
    if response['company_name'] == UNKNOWN_VALUE or response['document_date'] == DEFAULT_DATE or response['document_type'] == UNKNOWN_VALUE:
        logging.info("Insufficient information from first page. Checking second page.")
        text += "\n\n" + pdf_to_text(pdf_path, start_page=2, end_page=2)
        response = process_text_with_openai(text)
        
    if response['company_name'] == UNKNOWN_VALUE or response['document_date'] == DEFAULT_DATE or response['document_type'] == UNKNOWN_VALUE:
        logging.info("Still insufficient information. Checking third page.")
        text += "\n\n" + pdf_to_text(pdf_path, start_page=3, end_page=3)
        response = process_text_with_openai(text)
    
    return response
    
def process_text_with_openai(text: str) -> Dict[str, str]:
    """Process the extracted text with OpenAI API."""
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
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


def harmonize_company_name(company_name: str) -> str:
    """Harmonize company name based on predefined mappings."""
    company_name = company_name.strip()
    if not os.path.exists("harmonized-company-names.json"):
        logging.warning(f'harmonized-company-names.json not found, using original name: {company_name}')
        return company_name

    with open("harmonized-company-names.json", "r", encoding='utf-8') as file:
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

def process_pdf(pdf_path: str) -> None:
    """Process a single PDF file."""
    logging.info("---")
    logging.info(f"Processing {pdf_path}")
    openai_response = get_openai_response(pdf_path)
    company_name, document_date, document_type = parse_openai_response(openai_response)
    company_name = harmonize_company_name(company_name)
    rename_invoice(pdf_path, company_name, document_date, document_type)

def process_input(input_paths):
    """Process multiple input paths, which can be files or folders."""
    for input_path in input_paths:
        if os.path.isfile(input_path):
            if input_path.lower().endswith(PDF_EXTENSION):
                process_pdf(input_path)
            else:
                logging.warning(f"{input_path} is not a valid PDF.")
        elif os.path.isdir(input_path):
            for root, _, files in os.walk(input_path):
                for file in files:
                    if file.lower().endswith(PDF_EXTENSION):
                        process_pdf(os.path.join(root, file))
        else:
            logging.error(f"{input_path} is not a valid file or folder.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logging.error('Usage: python autorename.py <path_to_file_or_folder> [<path_to_file_or_folder> ...]')
        sys.exit(1)

    input_paths = sys.argv[1:]
    process_input(input_paths)