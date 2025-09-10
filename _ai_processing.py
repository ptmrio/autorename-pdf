"""
AI content processing and API calls for OpenAI and PrivateGPT.
This module handles the actual AI API calls and response processing.
"""

import os
import logging
import json
import re
import regex
from typing import Dict
from openai import OpenAI
from pgpt_python.client import PrivateGPTApi
from _ai_clients import get_client

# Constants
UNKNOWN_VALUE = "Unknown"
DEFAULT_DATE = "00000000"

def get_prompt_text():
    """Generate the prompt text for AI processing."""
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
    """Call the public OpenAI API using your API Key."""
    client = get_client()
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
    """Call the private GPT API."""
    client = get_client()
    try:
        response = client.contextual_completions.chat_completion(
            messages=[
                {
                    "role": "system", 
                    "content": get_prompt_text()
                },
                {
                    "role": "user", 
                    "content": f"Extract the information from the text:\n\n{text}"
                }
            ],
            use_context=False
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"PrivateGPT API call failed: {e}")
        raise

def post_process_private_ai_response(text: str, model: str) -> str:
    """Post-process PrivateGPT response to extract JSON."""
    render = None
    
    if model == 'ollama':
        json_regex = r'\{(?:[^{}]|(?R))*\}'
        match = regex.search(json_regex, text, regex.DOTALL)
        if match:
            render = match.group(0)
        else:
            # Fallback: try to find JSON without recursion
            simple_match = re.search(r'\{[^{}]*\}', text)
            if simple_match:
                render = simple_match.group(0)
            else:
                logging.warning(f"No JSON found in PrivateGPT response: {text[:200]}...")
                return text  # Return original if no JSON found
    else:
        logging.error(f"failed to load PRIVATEAI_POST_PROCESSOR {model}")
        raise Exception(f"failed to load PRIVATEAI_POST_PROCESSOR {model}")
    
    return render

def process_text_with_any_ai(text: str) -> Dict[str, str]:
    """Process text with any available AI client."""
    client = get_client()
    if client is None:
        raise ValueError("AI client not initialized. Call initialize_api_client first.")
    
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
            raise Exception(f'Unknown API client: {type(client)}')

        logging.info(f'Extract Response: {response}')
        parsed_response = json.loads(response)
        logging.info(f'API Extract Response: {parsed_response}')

        company_name = parsed_response.get('company_name', UNKNOWN_VALUE)
        document_date = parsed_response.get('document_date', DEFAULT_DATE)
        document_type = parsed_response.get('document_type', UNKNOWN_VALUE)

        # Import validation function from utils
        from _utils import is_valid_filename
        
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
