import os
import sys
import logging
import traceback
from _config_loader import load_yaml_config, config_to_env_mapping
from _ai_clients import initialize_openai_client, initialize_privateai_client, set_env_vars
from _ai_processing import process_text_with_any_ai
from _pdf_utils import pdf_to_text
from _document_processing import (
    harmonize_company_name,
    parse_ai_response,
    rename_invoice
)

# Constants
PDF_EXTENSION = ".pdf"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if getattr(sys, 'frozen', False):
    current_directory = os.path.dirname(sys.executable)  # Path to the folder containing the .exe
else:
    current_directory = os.path.dirname(os.path.abspath(__file__))  # Path to the script file

# Define the path to the config.yaml file
config_path = os.path.join(current_directory, 'config.yaml')

# Define the path to the harmonized-company-names.yaml file
yaml_path = os.path.join(current_directory, 'harmonized-company-names.yaml')


# Load configuration from the YAML file
config = load_yaml_config(config_path)
if not config:
    logging.error("Could not load configuration from config.yaml")
    sys.exit(1)

# Convert YAML config to environment variable format
env_vars = config_to_env_mapping(config)
set_env_vars(env_vars)


# Initialize OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
privateai_enabled = os.getenv("PRIVATEAI_ENABLED", "false").lower() in ['true', '1', 'yes', 'on']

if not openai_api_key and not privateai_enabled:
    logging.error("OPENAI_API_KEY not found in environment variables.")
    sys.exit(1)
    
# load the api client and make it available as global
if privateai_enabled:
    logging.info(f"PrivateAI client Enabled: %s" % privateai_enabled)
    initialize_privateai_client()
else:
    initialize_openai_client(openai_api_key)

def process_pdf(pdf_path: str, yaml_path: str) -> None:
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
        company_name = harmonize_company_name(company_name, yaml_path)
        rename_invoice(pdf_path, company_name, document_date, document_type)
    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {str(e)}")
        logging.debug(traceback.format_exc())

def process_input(input_paths):
    """Process multiple input paths, which can be files or folders (non-recursively)."""
    for input_path in input_paths:
        if os.path.isfile(input_path):
            if input_path.lower().endswith(PDF_EXTENSION):
                process_pdf(input_path, yaml_path)
            else:
                logging.warning(f"{input_path} is not a valid PDF.")
        elif os.path.isdir(input_path):
            for file in os.listdir(input_path):
                file_path = os.path.join(input_path, file)
                if os.path.isfile(file_path) and file.lower().endswith(PDF_EXTENSION):
                    process_pdf(file_path, yaml_path)
        else:
            logging.error(f"{input_path} is not a valid file or folder.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logging.error('Usage: python autorename.py <path_to_file_or_folder> [<path_to_file_or_folder> ...]')
        sys.exit(1)

    input_paths = sys.argv[1:]
    
    #test_parser()
    #input("Press Enter to exit...")
    process_input(input_paths)
    
    # Prevent the executable from closing immediately
    input("Press Enter to exit...")