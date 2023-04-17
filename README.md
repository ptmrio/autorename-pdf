# AIAutoRename

AIAutoRename is a Python script that automatically renames PDF files based on their content. It leverages the power of the [OpenAI GPT API](https://platform.openai.com/account/api-keys) to extract relevant information such as the document date, company name, and document type from the PDF's text. This tool is designed to simplify the organization and management of your PDF files by automating the renaming process.

## Installation

To use AIAutoRename, you'll need Python 3.6 or later. You can download it from the [official Python website](https://www.python.org/downloads/) or the Microsoft Store.

After installing Python, you can install the required packages by running the following command in your terminal:

```
pip install python-dotenv pdf2image pytesseract openai dateparser
```

Next, clone or download this repository and navigate to the root directory of the project in your terminal.

## Configuration

AIAutoRename uses environment variables to configure the OpenAI API key and the name of your company. Before running the script, you'll need to create a file named `.env` in the root directory of the project and add the following lines:

```
OPENAI_API_KEY=<your-api-key>
OPENAI_MODEL=gpt-3.5-turbo
MY_COMPANY_NAME=<your-company-name>
```

Replace `<your-api-key>` with your OpenAI API key, which can be obtained from the [OpenAI website](https://platform.openai.com/docs/developer-quickstart/your-api-keys). Set `<your-company-name>` to your company's name. This information will help the OpenAI API to better understand the context and decide whether to use the sender or recipient of the PDF document.

## Usage

### Renaming a single PDF file

To rename a single PDF file, run the following command in your terminal (cmd on Windows, terminal on Mac):

```
python autorename.py path/to/invoice.pdf
```

Replace `path/to/invoice.pdf` with the path to your PDF file.

**Example:**

Suppose your PDF file is named `invoice123.pdf` and is located in the `invoices` folder on your desktop. After running AIAutoRename, the file might be renamed to something like `20220101 ACME ER.pdf`, where `20220101` is the document date, `ACME` is the company name, and `ER` is the document type (incoming invoice).

### Renaming all PDF files in a folder

To rename all PDF files in a folder and its subfolders, run the following command in your terminal:

```
python autorename.py path/to/folder
```

Replace `path/to/folder` with the path to your folder (no trailing slash).

**Example:**

Suppose you have a folder named `invoices` on your desktop containing multiple PDF files. After running AIAutoRename on the folder, all PDF files within the folder and its subfolders will be renamed according to their content, such as document date, company name, and document type.

## Contributing

We welcome contributions from anyone! If you find a bug or have a feature request, please open an issue on our [GitHub repository](https://github.com/example/AIAutoRename). If you'd like to contribute code, please open a pull request with your changes. We appreciate your support in making AIAutoRename even better!
