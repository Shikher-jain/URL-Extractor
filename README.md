# FAQ Extraction and Viewer

This project is a Python application that extracts frequently asked questions (FAQs) from the official Python documentation and presents them in a user-friendly interface using Streamlit.

## Features

- Extracts FAQs from the Python documentation website.
- Cleans and formats the extracted data.
- Displays the FAQs in an interactive web application using Streamlit.
- Supports expandable sections for each question and answer.

## Requirements

- Python 3.x
- `requests` library
- `beautifulsoup4` library
- `streamlit` library

You can install the required libraries using pip:

```bash
pip install -r requirements.txt
```

## For Run

```bash

streamlit run model.py
```

## For Run Selenium Version

```bash

streamlit run app.py
```

## File Structure

```bash
URL_Extractor/
│
├── .gitignore           # add gitignore file to ignore big files like .html and .jsonl
├── app.py               # Selenium-based web scraper for Python documentation
├── model.py             # Streamlit application to display FAQs
├── requirements.txt     # All dependencies libraries
└── faqs.jsonl           # JSONL file containing the extracted FAQs
