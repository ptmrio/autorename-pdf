# autorename-pdf

**autorename-pdf** is a highly efficient tool designed to automatically rename and archive PDF documents based on their content. By leveraging OCR and AI technology, it extracts critical information such as the company name, document date, and document type to create well-organized filenames. This tool simplifies document management and ensures consistency, especially for businesses handling large volumes of PDFs.

---

## Features

- **Automatic PDF Renaming**: Extracts metadata from PDFs (company name, date, document type) and renames them accordingly.
- **Organized Archiving**: Ensures consistency in document naming and file storage, streamlining archiving processes.
- **Batch Processing**: Rename multiple PDFs within a folder in one go.
- **Context Menu Integration**: Easily right-click on files or folders to trigger renaming actions.
- **Powerful OCR Support**: Uses Tesseract and advanced AI via OpenAI for highly accurate text recognition from scanned PDFs.
- **Harmonized Company Names**: Converts extracted company names into a standardized format using a pre-defined mapping.

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
   - The setup script will:
     - Install **Chocolatey** if not already installed.
     - Install **Tesseract** and **Ghostscript** via Chocolatey.
     - Add AutoRenamePDF to the context menu for files and folders.

5. **Restart Your Computer**:
   - After the installation, restart your computer to apply all context menu changes.

---

## Configuration: Filling the `.env` File

The `.env` file must be properly filled out to configure the tool. Here's a breakdown of the required parameters:

1. **`OPENAI_API_KEY`**: 
   - This is your API key for accessing OpenAI's services (like GPT-4).
   - You can obtain your OpenAI API key by signing up at [OpenAI](https://platform.openai.com/signup).
   - After signing up, navigate to the API section and generate a new API key. Copy this key and paste it into your `.env` file like this:
     ```plaintext
     OPENAI_API_KEY=your-openai-api-key
     ```

2. **`OPENAI_MODEL`**:
   - Specifies which OpenAI model to use for OCR and content extraction. You can use models like `gpt-3.5-turbo` or `gpt-4` for higher accuracy.
   - Example:
     ```plaintext
     OPENAI_MODEL=gpt-4
     ```

3. **`MY_COMPANY_NAME`**:
   - This is your company name, which prevents the AI from extracting it repeatedly if it's a constant in your documents.
   - Example:
     ```plaintext
     MY_COMPANY_NAME=YourCompany
     ```

Make sure to save the `.env` file after making these changes.

### Example `.env` File:
```plaintext
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4
MY_COMPANY_NAME=YourCompany
```

---

## Usage

### Context Menu (Recommended)

Once installed, autorename-pdf can be accessed through the right-click context menu:

1. **Rename a Single PDF**: Right-click a PDF file and select `Auto Rename PDF` to automatically rename it.
2. **Batch Rename PDFs in Folder**: Right-click a folder and choose `Auto Rename PDFs in Folder` to process all PDFs within.
3. **Rename PDFs from Folder Background**: Right-click the background of a folder and select `Auto Rename PDFs in This Folder` to rename every PDF inside the folder.

### Command-Line Usage (Optional)

For command-line users, autorename-pdf can also be executed from the terminal:

- **Rename a single PDF**:
  ```bash
  autorename-pdf.exe "C:\path\to\file.pdf"
  ```

- **Rename all PDFs in a folder**:
  ```bash
  autorename-pdf.exe "C:\path\to\folder"
  ```

---

## Examples

Here are some real-world examples of how autorename-pdf can simplify your file management:

1. **Input**: `invoice_123.pdf`
   **Output**: `20230901 ACME ER.pdf`
   - Explanation: The file is renamed using the date `20230901` (1st September 2023), `ACME` as the company name, and `ER` for an incoming invoice.

2. **Input**: `payment_invoice.pdf`
   **Output**: `20231015 XYZ AR.pdf`
   - Explanation: The system extracts `20231015` (15th October 2023), `XYZ` as the company, and `AR` for an outgoing invoice.

3. **Batch Renaming**:
   - **Input**: A folder containing `invoice1.pdf`, `invoice2.pdf`, `invoice3.pdf`.
   - **Output**: Renamed files inside the folder as:
     - `20230712 CompanyA ER.pdf`
     - `20230713 CompanyB AR.pdf`
     - `20230714 CompanyC ER.pdf`

---

## Contribution and Support

We welcome contributions and feedback. If you have ideas or encounter issues, please submit a pull request or open an issue on [GitHub](https://github.com/ptmrio/autorename-pdf).

For any questions or support, please reach out through our GitHub page.