# autorename-pdf

**autorename-pdf** is a highly efficient tool designed to automatically rename and archive PDF documents based on their content. By leveraging OCR technology, it extracts critical information such as the company name, document date, and document type to create well-organized filenames. This tool simplifies document management and ensures consistency, especially for businesses handling large volumes of PDFs.

---

## Features

- **Automatic PDF Renaming**: Extracts metadata from PDFs (company name, date, document type) and renames them accordingly.
- **Organized Archiving**: Ensures consistency in document naming and file storage, streamlining archiving processes.
- **Batch Processing**: Rename multiple PDFs within a folder in one go.
- **Context Menu Integration**: Easily right-click on files or folders to trigger renaming actions.
- **Powerful OCR Support**: Uses Tesseract and advanced AI via OpenAI for highly accurate text recognition from scanned PDFs.

---

## Installation Guide

### Prerequisites

Ensure you have the following installed on your system:

1. **Python (OPTIONAL)**: Download and install the latest version of Python 3.x (preferably the latest version of Python 3, like 3.11):
   ```powershell
   winget install Python.Python
   ```


2. **Chocolatey**: Required for installing dependencies on Windows. Install it using PowerShell (run as administrator):
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
   ```   

2. **Tesseract OCR**: Required for extracting text from images in PDFs. Install it using winget (preferred):
   ```powershell
   choco install tesseract
   ```

3. **Poppler**: Required for converting PDF pages into images. Install via Chocolatey or manually:
    ```powershell
    choco install poppler
    ```

### Setup Instructions

1. **Download or clone the Repository**:
   ```cmd
   git clone https://github.com/ptmrio/autorename-pdf.git
   cd autorename-pdf
   ```

2. **Edit the `.env` File**:
   Configure your API key and company name by editing the `.env.example` file and move it into the dist folder as `.env.example`. Open it in any text editor and set the following:
   - Add your OpenAI API key:
     ```
     OPENAI_API_KEY=your-api-key
     ```
   - Specify your preferred OpenAI model:
     ```
     OPENAI_MODEL=gpt-4o
     ```
   - Enter your company name (this prevents it from being extracted):
     ```
     MY_COMPANY_NAME=your-company-name
     ```
   Save the file as `.env` after making these changes.

3. **Run the Context Menu Setup (Administrator Required)**:
   The app includes pre-built executables, so no need to install dependencies. Simply add the app to your context menu by running the following command (make sure to **run as admin**):
   ```cmd
   add-to-context-menu.exe
   ```

   This will add options to your right-click context menu for both individual PDFs and folders.

---

## Usage

### Context Menu (Recommended)

After installation, autorename-pdf can be accessed by right-clicking files or folders:

1. **Rename a Single PDF**: Right-click a PDF file and select `Auto Rename PDF` to automatically rename it.
2. **Batch Rename PDFs in Folder**: Right-click a folder and choose `Auto Rename PDFs in Folder` to process all PDFs within.
3. **Rename PDFs from Folder Background**: Right-click the background of a folder and select `Auto Rename PDFs in This Folder` to rename every PDF inside the folder.

### Command-Line Usage (Optional)

If you prefer using the terminal, autorename-pdf can be executed as a command-line tool:

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