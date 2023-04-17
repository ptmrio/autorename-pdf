import os
import sys
from pdf2image import convert_from_path
import pytesseract
import openai
import json
import dateparser
import re

openai.api_key = 

def pdf_to_text(pdf_path):
    images = convert_from_path(pdf_path)
    text = ''
    for image in images:
        text += pytesseract.image_to_string(image)
    return text

def get_openai_response(text):
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": f"Extract the company name, date, and document type from the following text:\n\n{text}"},
            {"role": "user", "content": "Return only a JSON object with these properties only `company_name`, `document_date`, `document_type`. No additional text."},
            {"role": "user", "content": "Do not include the legal type in the company name. Typical legal types are: AG, GmbH, e.U., KG, OG, etc. Always strip those from the company name."},
            {"role": "user", "content": "If the text language is German, assume a European date format (dd.mm.YYYY or dd/mm/YYYY or reverse) in the text. Return format: dd.mm.YYYY"},
            {"role": "user", "content": "Valid document types are: For Invoices use the term 'ER' only, nothing more. For all other documents, find a short descriptive summary/subject in german language."},
        ]
    )
    response = completion.choices[0].message["content"]
    print(response)
    return json.loads(response)


def parse_openai_response(response):
    company_name = response.get('company_name', 'Unknown')
    date = dateparser.parse(response.get('document_date', '00000000'), settings={'DATE_ORDER': 'DMY'})
    document_type = response.get('document_type', 'Unknown')

    return company_name, date, document_type

def rename_invoice(pdf_path, company_name, date, document_type):
    new_name = f'{date.strftime("%Y%m%d")} {company_name} {document_type}.pdf'
    new_path = os.path.join(os.path.dirname(pdf_path), new_name)
    os.rename(pdf_path, new_path)
    print(f'Invoice renamed to: {new_name}')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python autorename_invoices.py <path_to_invoice.pdf>')
        sys.exit(1)

    pdf_path = sys.argv[1]
    text = pdf_to_text(pdf_path)
    openai_response = get_openai_response(text)
    company_name, date, document_type = parse_openai_response(openai_response)
    rename_invoice(pdf_path, company_name, date, document_type)
