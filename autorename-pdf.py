import os
import sys
import logging
from dotenv import load_dotenv
from pdf_processor import process_pdf, PDF_EXTENSION, initialize_openai_client


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

# Initialize OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logging.error("OPENAI_API_KEY not found in environment variables.")
    sys.exit(1)

initialize_openai_client(openai_api_key)

def process_input(input_paths):
    """Process multiple input paths, which can be files or folders."""
    for input_path in input_paths:
        if os.path.isfile(input_path):
            if input_path.lower().endswith(PDF_EXTENSION):
                process_pdf(input_path, json_path)
            else:
                logging.warning(f"{input_path} is not a valid PDF.")
        elif os.path.isdir(input_path):
            for root, _, files in os.walk(input_path):
                for file in files:
                    if file.lower().endswith(PDF_EXTENSION):
                        process_pdf(os.path.join(root, file), json_path)
        else:
            logging.error(f"{input_path} is not a valid file or folder.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logging.error('Usage: python autorename.py <path_to_file_or_folder> [<path_to_file_or_folder> ...]')
        sys.exit(1)

    input_paths = sys.argv[1:]
    process_input(input_paths)