AIAutoRename
==========

AIAutoRename is a Python script that automatically renames PDF files based on their content. It uses the [OpenAI GPT API](https://platform.openai.com/account/api-keys) to extract relevant information such as the document date, company name, and document type from the PDF's text.

Installation
------------

To use AIAutoRename, you'll need Python 3.6 or later. You can download it from the [official Python website](https://www.python.org/downloads/) or the Microsoft Store.

After installing Python, you can install the required packages by running the following command in your terminal:

`pip install python-dotenv pdf2image pytesseract openai dateparser`

Now clone or download this repository and navigate to the root directory of the project in your terminal.

Configuration
-------------

AIAutoRename uses environment variables to configure the OpenAI API key and the name of your company. Before running the script, you'll need to create a file named `.env` in the root directory of the project and add the following lines:


```
OPENAI_API_KEY=<your-api-key>
MY_COMPANY_NAME=<your-company-name>
```

You can obtain an API key from the [OpenAI website](https://beta.openai.com/docs/developer-quickstart/your-api-keys). The `MY_COMPANY_NAME` variable should be set to your company's name. This will let the OpenAI API know, who you are so it can decide whether to use the sender or recepient of the pdf document.

Usage
-----

### Renaming a single PDF file

To rename a single PDF file, run the following command in your terminal (cmd on Windows, terminal on Mac):

`python AIAutoRename.py path/to/invoice.pdf`

Replace `path/to/invoice.pdf` with the path to your PDF file.

### Renaming all PDF files in a folder

To rename all PDF files in a folder and its subfolders, run the following command in your terminal:

`python AIAutoRename.py path/to/folder`

Replace `path/to/folder` with the path to your folder (no trailing slash).

Contributing
------------

We welcome contributions from anyone! If you find a bug or have a feature request, please open an issue on our [GitHub repository](https://github.com/example/AIAutoRename). If you'd like to contribute code, please open a pull request with your changes.