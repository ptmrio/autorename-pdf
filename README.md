# AutoRename-PDF

**AutoRename-PDF** is a powerful tool that automatically renames and archives PDF documents based on their content. Using OCR and AI technology, it extracts key information like company names, dates, and document types to create organized filenames, simplifying document management for businesses handling large volumes of PDFs.

## Features

-   **Automatic PDF Renaming** - Extracts metadata and renames PDFs with structured filenames
-   **Public & Private AI Support** - Choose between OpenAI GPT or your local private GPT instance
-   **Customizable Output** - Configure date formats, language preferences, and document type abbreviations
-   **Batch Processing** - Rename multiple PDFs in folders with one action
-   **Context Menu Integration** - Right-click files or folders to trigger renaming
-   **Powerful OCR** - Uses Tesseract and AI for accurate text recognition from scanned PDFs
-   **Company Name Harmonization** - Standardizes company names using customizable mappings

## Configuration

Create a `config.yaml` file in the project directory with the following configuration:

```yaml
# OpenAI Configuration
openai:
    api_key: "your-openai-api-key" # Get from https://platform.openai.com/
    model: "gpt-5" # Model to use: gpt-5, gpt-4o, gpt-3.5-turbo, ...

# Company Information
company:
    name: "Your Company Name" # Your company name (prevents duplicate extraction)

# PDF Processing Configuration
pdf:
    outgoing_invoice: "AR" # Abbreviation for outgoing invoices (Accounts Receivable)
    incoming_invoice: "ER" # Abbreviation for incoming invoices (Expense Reports)

# Language and Localization Settings
output_language: "English" # Main language of your PDFs
date_format: "%Y%m%d" # Date format using strftime (YYYYMMDD)
ocr_languages: "eng,deu" # Tesseract language codes (comma-separated)

# Optional AI Prompt Enhancement
prompt_extension: 'If it is an incoming or outgoing invoice, add the total amount to the document_type like "AR 12,34" or "ER 56,78".'

# Private AI Configuration (Optional)
private_ai:
    enabled: false # Set to true to use private GPT instead of OpenAI
    scheme: "http" # Connection scheme for private AI
    host: "localhost" # Private AI host address
    port: 8001 # Private AI port number
    timeout: 720 # Timeout in seconds
    post_processor: "ollama" # Post processor type
```

**Note**: For `ocr_languages`, you need to re-run the setup script after changing this parameter to download the required language data.

## Installation

### Prerequisites

-   **Administrator Rights** - Required for setup
-   **Windows System** - Chocolatey, Tesseract, and Ghostscript will be auto-installed

### Setup Instructions

1. **Download the latest release** from [GitHub Releases](https://github.com/ptmrio/autorename-pdf/releases)

2. **Extract the ZIP file** to your desired location

3. **Run setup as administrator**:

    ```powershell
    # Open PowerShell as Administrator
    cd "C:\path\to\extracted\folder"
    PowerShell -ExecutionPolicy Bypass -File .\setup.ps1
    ```

4. **Restart your computer** to apply context menu changes

The setup script will automatically:

-   Install Chocolatey (if needed)
-   Install Tesseract and Ghostscript
-   Download OCR language data
-   Add context menu integration

### Private AI Prerequisites (EXPERIMENTAL ⚠️, Optional)

If using `PRIVATEAI_ENABLED=true`, you need a private GPT environment:

-   Docker image: `zylonai/private-gpt:0.6.2-ollama`
-   Follow setup guide: [PrivateGPT Quickstart](https://docs.privategpt.dev/quickstart/getting-started/quickstart)
-   **Note**: On Windows 11 Pro, Ghostscript 10.02.1 works best for PDF processing

### Troubleshooting

If you encounter issues, ensure these paths are in your system PATH:

-   `C:\Program Files\Tesseract-OCR`
-   `C:\Program Files\gs\gsVERSION_NUMBER\bin`

For debugging, run `autorename-pdf` from the command line to see error messages.

## Usage

### Context Menu (Recommended)

After installation, right-click to access AutoRename-PDF:

-   **Single PDF**: Right-click a PDF → `Auto Rename PDF`
-   **Folder of PDFs**: Right-click a folder → `Auto Rename PDFs in Folder`
-   **Current Folder**: Right-click folder background → `Auto Rename PDFs in This Folder`

### Command Line

```bash
# Rename single PDF
autorename-pdf.exe "C:\path\to\file.pdf"

# Rename all PDFs in folder
autorename-pdf.exe "C:\path\to\folder"
```

## Company Name Harmonization

Standardize company name variations using `harmonized-company-names.yaml`:

```yaml
# Harmonized Company Names
# This file maps various company name variations to standardized names

ACME:
    - "ACME Corp"
    - "ACME Inc."
    - "ACME Corporation"
    - "ACME Company"

XYZ:
    - "XYZ Ltd"
    - "XYZ LLC"
    - "XYZ Enterprises"
    - "XYZ Solutions"
```

This converts various company name formats into consistent standards for better file organization. The YAML format is much more readable and easier to maintain than JSON.

### 💡 Quick Tip: Generate Company Names with AI

You can easily create your harmonized company names file by using AI tools like Google Gemini, ChatGPT, or Claude:

1. **Collect your document filenames**: On Windows, select multiple PDF files, right-click and choose "Copy path"
2. **Extract just the filenames**: Paste the paths into any text editor and use find/replace to remove the directory paths, keeping only the filenames
3. **Use AI to generate the YAML**: Paste the filenames into an AI tool with this prompt:

    _"Please analyze these PDF filenames and create a harmonized-company-names.yaml file that maps different variations of company names to standardized names. Use the format shown in the example file below:"_

    Then include the contents of `harmonized-company-names.yaml.example` as reference.

4. **Save and customize**: Save the AI-generated content as `harmonized-company-names.yaml` and adjust as needed.

This method leverages AI pattern recognition to quickly identify company name variations from your existing documents, saving you time in manual mapping.

## Examples

### Basic Renaming

-   **Input**: `invoice_123.pdf`
-   **Output**: `20230901 ACME INVOICE.pdf`

### With Amount Extension

Using `PROMPT_EXTENSION` to include totals:

-   **Input**: `payment_invoice.pdf`
-   **Output**: `20231015 XYZ EARNING 1,234.56.pdf`

### Custom Date Format

With `OUTPUT_DATE_FORMAT=%Y-%m-%d`:

-   **Input**: `invoice_789.pdf`
-   **Output**: `2023-09-10 ACME INVOICE.pdf`

### Batch Processing

-   **Input Folder**: `invoice1.pdf`, `invoice2.pdf`, `invoice3.pdf`
-   **Output**:
    -   `20230712 CompanyA INVOICE.pdf`
    -   `20230713 CompanyB EARNING.pdf`
    -   `20230714 CompanyC INVOICE.pdf`

## Support the Project

If you use AutoRename-PDF for your business, you are probably saving hours of work or even lots of money by saving on workforce costs. This tool automates tedious manual PDF renaming tasks that would otherwise require significant time and human resources.

**Consider supporting the project:**

-   ⭐ [Star the repository](https://github.com/ptmrio/autorename-pdf) on GitHub
-   💖 [Sponsor on GitHub](https://github.com/sponsors/ptmrio)
-   ☕ [Donate via PayPal](https://www.paypal.com/paypalme/Petermeir)

Your support helps maintain and improve this free tool that benefits businesses worldwide!

### 🙏 Thank You to Our Supporters

We're grateful to the following contributors who have supported AutoRename-PDF:

-   [@claus82](https://github.com/claus82) - Thank you for your generous donation! 💖

Your support makes it possible to continue developing and maintaining this tool for the community.


## Support & Contributions

For questions or support, visit our [GitHub repository](https://github.com/ptmrio/autorename-pdf) and open an issue.

### Contributing

While we appreciate your interest in improving AutoRename-PDF, we're currently not accepting direct contributions to maintain project consistency and direction. However, you're welcome to:

-   **Open an issue** to report bugs, request features, or ask questions
-   **Create your own fork** to customize the tool for your specific needs
-   **Share feedback** about your experience using the tool

Thank you for understanding and for your interest in the project!

---

_AutoRename-PDF simplifies document management through intelligent, automated file organization._
