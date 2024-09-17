# AutoRename-PDF

**AutoRename-PDF** is a highly efficient tool designed to automatically rename and archive PDF documents based on their content. By leveraging OCR and AI technology, it extracts critical information such as the company name, document date, and document type to create well-organized filenames. This tool simplifies document management and ensures consistency, especially for businesses handling large volumes of PDFs.

---

## Features

- **Automatic PDF Renaming**: Extracts metadata from PDFs (company name, date, document type) and renames them accordingly.
- **Customizable Output Format**: Configure date formats, language preferences, and document type abbreviations to suit your needs.
- **Organized Archiving**: Ensures consistency in document naming and file storage, streamlining archiving processes.
- **Batch Processing**: Rename multiple PDFs within a folder in one go.
- **Context Menu Integration**: Easily right-click on files or folders to trigger renaming actions.
- **Powerful OCR Support**: Uses Tesseract and advanced AI via OpenAI for highly accurate text recognition from scanned PDFs.
- **Harmonized Company Names**: Converts extracted company names into a standardized format using a pre-defined mapping.

---

## Configuration: Filling the `.env` File

The `.env` file must be properly filled out to configure the tool. Below is a breakdown of all the parameters you can set:

### Required Parameters

1. **`OPENAI_API_KEY`**:

   - Your API key for accessing OpenAI's services (like GPT-4).
   - You can obtain your OpenAI API key by signing up at [OpenAI](https://platform.openai.com/signup).
   - After signing up, navigate to the API section and generate a new API key. Copy this key and paste it into your `.env` file:
     ```plaintext
     OPENAI_API_KEY=your-openai-api-key
     ```

2. **`OPENAI_MODEL`**:

   - Specifies which OpenAI model to use for OCR and content extraction. Options include `gpt-3.5-turbo` or `gpt-4`.
   - Example:
     ```plaintext
     OPENAI_MODEL=gpt-4o
     ```

3. **`MY_COMPANY_NAME`**:

   - Your company name, which prevents the AI from extracting it repeatedly if it's a constant in your documents.
   - Example:
     ```plaintext
     MY_COMPANY_NAME=YourCompany
     ```

4. **`PDF_OUTGOING_INVOICE`**:

   - Default abbreviation for outgoing invoices (e.g., `EARNING`).
   - Example:
     ```plaintext
     PDF_OUTGOING_INVOICE=EARNING
     ```

5. **`PDF_INCOMING_INVOICE`**:

   - Default abbreviation for incoming invoices (e.g., `INVOICE`).
   - Example:
     ```plaintext
     PDF_INCOMING_INVOICE=INVOICE
     ```

6. **`OUTPUT_LANGUAGE`**:

   - The main language of most of the PDFs, used to optimize AI prompts.
   - Example:
     ```plaintext
     OUTPUT_LANGUAGE=English
     ```

7. **`OUTPUT_DATE_FORMAT`**:

   - Date format for the output file name, following [strftime](https://strftime.org/) conventions.
   - Example (for YYYYMMDD format):
     ```plaintext
     OUTPUT_DATE_FORMAT=%Y%m%d
     ```

8. **`PROMPT_EXTENSION`**:

   - Optional instructions to fine-tune the AI prompt that extracts the invoice details.
   - Example:
     ```plaintext
     PROMPT_EXTENSION=If it is an incoming or outgoing invoice, add the total amount to the document_type like "EARNING 12,34" or "INVOICE 56,78".
     ```

9. **`OCR_LANGUAGES`**:

   - Comma-separated list of 3-letter language codes for Tesseract OCR. Ensure the appropriate language data is installed.
   - **Note**: You need to re-run the setup script after changing this parameter to download the required language data.
   - Example (for German and English):
     ```plaintext
     OCR_LANGUAGES=deu,eng
     ```

Make sure to save the `.env` file after making these changes.

---

## Installation Guide

### Prerequisites

Before starting, ensure the following:

- **Administrator Rights**: You must run the setup as an administrator for successful installation.
- **Chocolatey, Tesseract, and Ghostscript**: These will be automatically installed if not already present.

### Setup Instructions

1. **Download the Latest Release**:

   - Go to the [AutoRename-PDF GitHub Releases](https://github.com/ptmrio/autorename-pdf/releases) page.
   - Download the latest `.zip` file.

2. **Extract the ZIP Folder**:

   - Extract the downloaded `.zip` file to your desired location.

3. **Run the Setup Script**:

   - Open **PowerShell with Administrator Rights**.
   - Navigate to the extracted folder using the following command:
     ```powershell
     cd "C:\path\to\extracted\folder"
     ```
   - Run the setup script:
     ```powershell
     PowerShell -ExecutionPolicy Bypass -File .\setup.ps1
     ```

4. **Follow the Installation Steps**:

   - The setup script will automatically:
     - Install **Chocolatey** if not already installed.
     - Install **Tesseract** and **Ghostscript** via Chocolatey.
     - Download **language data** for Tesseract as specified in your configuration.
     - Add AutoRename-PDF to the context menu for files and folders.

5. **Restart Your Computer**:
   - After the installation, restart your computer to apply all context menu changes.

**Troubleshooting**: Make sure Tesseract and Ghostscript got added to your system's PATH. If not, add `C:\Program Files\Tesseract-OCR` (typically) and `C:\Program Files\gs\gsVERSION_NUMBER\bin` (typically) to your system's PATH manually. Replace `VERSION_NUMBER` with the installed Ghostscript version. Also, ensure to configure the `.env` file correctly (see below). If you still encounter any issues, please open the terminal and use `autorename-pdf` from the command line to see the error messages.

### Example `.env` File:

```plaintext
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o
MY_COMPANY_NAME=YourCompany
PDF_OUTGOING_INVOICE=EARNING
PDF_INCOMING_INVOICE=INVOICE
OUTPUT_LANGUAGE=English
OUTPUT_DATE_FORMAT=%Y%m%d
PROMPT_EXTENSION=If it is an incoming or outgoing invoice, add the total amount to the document_type like "AR 12,34" or "ER 56,78".
OCR_LANGUAGES=eng,deu
```

---

## Usage

### Context Menu (Recommended)

Once installed, AutoRename-PDF can be accessed through the right-click context menu:

1. **Rename a Single PDF**: Right-click a PDF file and select `Auto Rename PDF` to automatically rename it.
2. **Batch Rename PDFs in Folder**: Right-click a folder and choose `Auto Rename PDFs in Folder` to process all PDFs within.
3. **Rename PDFs from Folder Background**: Right-click the background of a folder and select `Auto Rename PDFs in This Folder` to rename every PDF inside the folder.

### Command-Line Usage (Optional)

For command-line users, AutoRename-PDF can also be executed from the terminal:

- **Rename a single PDF**:

  ```bash
  autorename-pdf.exe "C:\path\to\file.pdf"
  ```

- **Rename all PDFs in a folder**:
  ```bash
  autorename-pdf.exe "C:\path\to\folder"
  ```

**Tip**: Add the `autorename-pdf.exe` path to your system's PATH for easier access from the command line.

---

## Harmonized Company Names

The **harmonized company names** feature allows you to convert AI-extracted company names into a standardized format. This is particularly useful when working with various company name variants, ensuring consistent naming conventions in the output.

For example:

- **Input**: `ACME Corp`, `ACME Inc.`, `ACME Corporation`
- **Output**: `ACME`

This helps maintain uniformity in your archived files, improving searchability and organization. The harmonized company names are configured using a JSON file (`harmonized-company-names.json`), where you can map different variations of a company name to a standard name.

### Example `harmonized-company-names.json`:

```json
{
  "ACME": ["ACME Corp", "ACME Inc.", "ACME Corporation"],
  "XYZ": ["XYZ Ltd", "XYZ LLC", "XYZ Enterprises"]
}
```

---

## Examples

Here are some real-world examples of how AutoRename-PDF can simplify your file management:

1. **Standard Renaming**:

   - **Input**: `invoice_123.pdf`
   - **Output**: `20230901 ACME ER.pdf`
   - **Explanation**: The file is renamed using the date `20230901` (1st September 2023), `ACME` as the company name, and `ER` for an incoming invoice.

2. **Outgoing Invoice with Custom Abbreviation**:

   - **Input**: `payment_invoice.pdf`
   - **Output**: `20231015 XYZ AR.pdf`
   - **Explanation**: The system extracts `20231015` (15th October 2023), `XYZ` as the company, and `AR` for an outgoing invoice.

3. **Including Total Amount in Document Type**:

   - With the `PROMPT_EXTENSION` configured to include the total amount:
     ```plaintext
     PROMPT_EXTENSION=If it is an incoming or outgoing invoice, add the total amount to the document_type like "AR 12,34" or "ER 56,78".
     ```
   - **Input**: `invoice_456.pdf`
   - **Output**: `20230905 ACME ER 56,78.pdf`
   - **Explanation**: The total amount `56,78` is appended to the document type `ER`.

4. **Custom Date Format**:

   - With `OUTPUT_DATE_FORMAT` set to include dashes:
     ```plaintext
     OUTPUT_DATE_FORMAT=%Y-%m-%d
     ```
   - **Input**: `invoice_789.pdf`
   - **Output**: `2023-09-10 ACME ER.pdf`
   - **Explanation**: The date is formatted as `YYYY-MM-DD`.

5. **Batch Renaming**:

   - **Input**: A folder containing `invoice1.pdf`, `invoice2.pdf`, `invoice3.pdf`.
   - **Output**: Renamed files inside the folder as:
     - `20230712 CompanyA ER.pdf`
     - `20230713 CompanyB AR.pdf`
     - `20230714 CompanyC ER.pdf`

---

## Contribution and Support

We welcome contributions and feedback. If you have ideas or encounter issues, please submit a pull request or open an issue on [GitHub](https://github.com/ptmrio/autorename-pdf).

For any questions or support, please reach out through our GitHub page.
