AIAutoRename
============

AIAutoRename is a Python script that automatically renames PDF files based on their content. It leverages the power of the OpenAI GPT Chat API to extract relevant information, such as the document date, company name, and document type, from the PDF's text. This tool is designed to simplify the organization and management of your PDF files by automating the renaming process.

Installation
------------

To use AIAutoRename, you'll need Python 3.6 or later. You can download it from the [official Python website](https://www.python.org/downloads/) or the Microsoft Store.

1.  Clone or download this repository and navigate to the root directory of the project in your terminal.
    
2.  Install the required packages using the `requirements.txt` file:
    

```
pip install -r requirements.txt
```

3.  Install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/) for Windows by following the installation instructions on their GitHub page. During the installation process, ensure that the "Add tesseract to PATH" option is checked. This will automatically add Tesseract to your PATH environment variable.
    
4.  Download and install [poppler for Windows](https://github.com/oschwartz10612/poppler-windows). After installation, add the `bin` folder of the installed poppler directory to your PATH environment variable. Here's a [guide](https://www.architectryan.com/2018/03/17/add-to-the-path-on-windows-10/) on how to add directories to the PATH variable on Windows 10.
    

Configuration
-------------

AIAutoRename uses environment variables to configure the OpenAI API key and the name of your company. Before running the script, you'll need to create a file named `.env` in the root directory of the project and add the following lines:

```
OPENAI_API_KEY=<your-api-key>
OPENAI_MODEL=gpt-3.5-turbo
MY_COMPANY_NAME=<your-company-name>
```

Replace `<your-api-key>` with your OpenAI API key, which can be obtained from the [OpenAI website](https://platform.openai.com/docs/developer-quickstart/your-api-keys). Set `<your-company-name>` to your company's name. This information will help the OpenAI API to better understand the context and decide whether to use the sender or recipient of the PDF document.

Usage
-----

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

Suppose you have a folder named `invoices` on your desktop containing multiple PDF files. After running AIAutoRename on the folder, all PDF files within the folder and its subfolders will be renamed according to their content, such as document date, company name, and document type. For example, a file originally named `invoice123.pdf` might be renamed to `20220215 MegaCorp PO.pdf`, where `20220215` is the document date, `MegaCorp` is the company name, and `PO` is the document type (purchase order).

Contributing
------------

We welcome contributions from everyone! If you find a bug or have a feature request, please open an issue on our [GitHub repository](https://github.com/example/AIAutoRename). If you'd like to contribute code, please open a pull request with your changes. We appreciate your support in making AIAutoRename even better!

Support
-------

If you encounter any issues or need assistance using AIAutoRename, please don't hesitate to reach out by opening an issue on our [GitHub repository](https://github.com/example/AIAutoRename). We'll do our best to help you as soon as possible.