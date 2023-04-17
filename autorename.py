import os
from dotenv import load_dotenv
import sys
from pdf2image import convert_from_path
import pytesseract
import openai
import json
import dateparser
import re

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
my_company_name = os.getenv("MY_COMPANY_NAME")


def pdf_to_text(pdf_path):
    images = convert_from_path(pdf_path, first_page=1, last_page=1)
    text = ''
    for image in images:
        text += pytesseract.image_to_string(image)
    return text


def truncate_text(text, max_tokens=2048):
    tokens = text.split()
    truncated_text = ' '.join(tokens[:max_tokens])
    return truncated_text


def is_valid_filename(filename: str) -> bool:
    forbidden_characters = r'[<>:"/\\|?*]'
    return not re.search(forbidden_characters, filename)


def get_openai_response(text):
    max_attempts = 3
    attempt = 0

    while attempt < max_attempts:
        print(f'Attempt {attempt+1}/{max_attempts}')
        print('---------------------------------')
        print('PDF text (preview):')
        print({text[:1000]})
        print('---------------------------------')

        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content":
                        "You will be asked to extract the company name, document date, and document type from a PDF document." +
                        "Due to the nature of OCR, the text will be very noisy and might contain spelling errors, handle those as good as possible." +
                        "You will only return a JSON object with these properties only \"company_name\", \"document_date\", \"document_type\"." +
                        "No additional text and no formatting. Only the JSON object." +
                        "If the text language is German, assume a European date format (dd.mm.YYYY or dd/mm/YYYY or reverse) in the text. Return format: dd.mm.YYYY" +
                        "Valid document types are: For Invoices use the term 'ER' only, nothing more. For all other documents, find a short descriptive summary/subject in german language." +
                        "Here are three example responses for training purpose only:" +
                        "{\"company_name\": \"ACME\", \"document_date\": \"01.01.2021\", \"document_type\": \"ER\"} " +
                        "{\"company_name\": \"ACME\", \"document_date\": \"01.01.2021\", \"document_type\": \"Einzahlungsbestätigung\"} " +
                        "{\"company_name\": \"ACME\", \"document_date\": \"01.01.2021\", \"document_type\": \"Angebot\"}"
                },
                {"role": "user", "content": f"Extract the \"company_name\", \"document_date\", \"document_type\" from this PDF document and reply with a JSON object:\n\n{text}"},
            ]
        )

        response = completion.choices[0].message["content"]

        print('---------------------------------')
        print('API Response:')
        print(response)
        print('---------------------------------')

        try:
            json_response = json.loads(response)
            if ('company_name' in json_response and 'document_date' in json_response and 'document_type' in json_response):
                company_name = json_response['company_name']
                document_date = json_response['document_date']
                document_type = json_response['document_type']

                date = dateparser.parse(document_date, settings={
                                        'DATE_ORDER': 'DMY'
                                        })

                if (is_valid_filename(company_name) and is_valid_filename(document_type) and date):
                    break

        except json.JSONDecodeError:
            pass

        attempt += 1

    if attempt == max_attempts:
        return {"company_name": "Unknown", "document_date": "00000000", "document_type": "Unknown"}

    return json_response


def parse_openai_response(response):
    company_name = response.get('company_name', 'Unknown')
    date = dateparser.parse(response.get(
        'document_date', '00000000'), settings={'DATE_ORDER': 'DMY'})
    document_type = response.get('document_type', 'Unknown')

    return company_name, date, document_type


def rename_invoice(pdf_path, company_name, date, document_type):
    base_name = f'{date.strftime("%Y%m%d")} {company_name} {document_type}'
    counter = 0
    new_name = base_name + '.pdf'
    new_path = os.path.join(os.path.dirname(pdf_path), new_name)

    if pdf_path == new_path:
        print(f'File "{new_name}" is already correctly named.')
        return

    while os.path.exists(new_path):
        counter += 1
        new_name = f'{base_name} ({counter}).pdf'
        new_path = os.path.join(os.path.dirname(pdf_path), new_name)

    try:
        os.rename(pdf_path, new_path)
        print(f'Invoice renamed to: {new_name}')
    except Exception as e:
        print(f'Error renaming {pdf_path}: {str(e)}')


def process_folder(folder_path):
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_path = os.path.join(root, file)
                text = pdf_to_text(pdf_path)
                openai_response = get_openai_response(text)
                company_name, date, document_type = parse_openai_response(
                    openai_response)
                rename_invoice(pdf_path, company_name, date, document_type)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python autorename.py <path_to_invoice.pdf> or <path_to_folder>')
        sys.exit(1)

    input_path = sys.argv[1]

    if os.path.isfile(input_path) and input_path.lower().endswith('.pdf'):
        text = pdf_to_text(input_path)
        openai_response = get_openai_response(text)
        company_name, date, document_type = parse_openai_response(
            openai_response)
        rename_invoice(input_path, company_name, date, document_type)
    elif os.path.isdir(input_path):
        process_folder(input_path)
    else:
        print('Invalid input. Please provide a path to a PDF file or a folder.')
        sys.exit(1)
