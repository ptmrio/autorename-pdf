import os
import sys
import logging
from dotenv import load_dotenv
from pdf_processor import process_pdf, PDF_EXTENSION, initialize_openai_client, set_env_vars
from pdf_processor import initialize_privateai_client

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if getattr(sys, 'frozen', False):
    current_directory = os.path.dirname(sys.executable)  # Path to the folder containing the .exe
else:
    current_directory = os.path.dirname(os.path.abspath(__file__))  # Path to the script file

# Define the path to the .env file
env_path = os.path.join(current_directory, '.env')

# Define the path to the harmonized-company-names.json file
json_path = os.path.join(current_directory, 'harmonized-company-names.json')


# Load environment variables from the .env file
load_dotenv(env_path)
env_vars = {
    'OPENAI_MODEL': os.getenv('OPENAI_MODEL'),
    'OCR_LANGUAGES': os.getenv('OCR_LANGUAGES'),
    'OUTPUT_LANGUAGE': os.getenv('OUTPUT_LANGUAGE'),
    'PDF_INCOMING_INVOICE': os.getenv('PDF_INCOMING_INVOICE'),
    'PDF_OUTGOING_INVOICE': os.getenv('PDF_OUTGOING_INVOICE'),
    'MY_COMPANY_NAME': os.getenv('MY_COMPANY_NAME'),
    'OUTPUT_DATE_FORMAT': os.getenv('OUTPUT_DATE_FORMAT'),
    'PROMPT_EXTENSION': os.getenv('PROMPT_EXTENSION'),
    'PRIVATEAI_ENABLED': os.getenv('PRIVATEAI_ENABLED'),
    'PRIVATEAI_SCHEME': os.getenv('PRIVATEAI_SCHEME'),
    'PRIVATEAI_HOST': os.getenv('PRIVATEAI_HOST'),
    'PRIVATEAI_PORT': os.getenv('PRIVATEAI_PORT'),
    'PRIVATEAI_TIMEOUT': os.getenv('PRIVATEAI_TIMEOUT'),
    'PRIVATEAI_POST_PROCESSOR': os.getenv('PRIVATEAI_POST_PROCESSOR'),
 }

set_env_vars(env_vars)


# Initialize OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
privateai_enabled = os.getenv("PRIVATEAI_ENABLED",False)
if not openai_api_key and not privateai_enabled:
    logging.error("OPENAI_API_KEY not found in environment variables.")
    sys.exit(1)
    
# load the api client and make it available as global
if privateai_enabled:
    logging.info(f"PrivateAI client Enabled: %s" % privateai_enabled)
    initialize_privateai_client()
else:
    initialize_openai_client(openai_api_key)

def process_input(input_paths):
    """Process multiple input paths, which can be files or folders (non-recursively)."""
    for input_path in input_paths:
        if os.path.isfile(input_path):
            if input_path.lower().endswith(PDF_EXTENSION):
                process_pdf(input_path, json_path)
            else:
                logging.warning(f"{input_path} is not a valid PDF.")
        elif os.path.isdir(input_path):
            for file in os.listdir(input_path):
                file_path = os.path.join(input_path, file)
                if os.path.isfile(file_path) and file.lower().endswith(PDF_EXTENSION):
                    process_pdf(file_path, json_path)
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