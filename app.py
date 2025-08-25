import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import json
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Attempt to import requests_html, a fallback for some dynamic sites
try:
    from requests_html import HTMLSession
except ImportError:
    HTMLSession = None

# --- Configuration ---
DATA_FILE = "faqs.json"

# --- Helper Functions ---

def clean_text(text: str) -> str:
    # Clean unwanted symbols and normalize spaces.
    text = re.sub(r"[¶Â]", "", text)
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\xa0", " ", text)
    return text.strip()

def get_page_source_selenium(url: str) -> str:
    # Fetches the page source using a headless Selenium browser.
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    time.sleep(5)  # Wait for JS to load
    
    page_source = driver.page_source
    driver.quit()
    return page_source

def remove_noisy_tags(soup):
    """Removes irrelevant tags to clean up the HTML."""
    for tag in soup(["script", "style", "nav", "footer", "header", "form",
                     "noscript", "iframe", "button", "input", "aside"]):
        tag.decompose()
    return soup

# --- Extraction Logic (Combined and Prioritized) ---

def extract_faqs_from_html(html: str) -> list:
    """Combines extraction logic from all scripts."""
    faqs = []
    
    soup = BeautifulSoup(html, "html.parser")
    soup = remove_noisy_tags(soup)
    text = soup.get_text(separator="\n", strip=True)
    
    # 1. Look for explicit Q: and A: patterns (from test.py & model.py)
    # This is a robust regex that works for multi-line Q/A.
    qna = re.findall(r"Q(?:uestion)?:?\s*(.*?)(?:A(?:nswer)?:)?\s*(.*?)(?=\nQ|\Z)", text, re.I | re.S)
    for q, a in qna:
        if q.strip() and a.strip():
            faqs.append({"question": clean_text(q), "answer": clean_text(a)})

    if faqs:
        return faqs

    # 2. Look for <dt> and <dd> tags (from test.py & model.py)
    for dt, dd in zip(soup.find_all("dt"), soup.find_all("dd")):
        q = dt.get_text(strip=True)
        a = dd.get_text(strip=True)
        if q and a:
            faqs.append({"question": q, "answer": a})

    if faqs:
        return faqs

    # 3. Look for header followed by a paragraph (from test.py & model.py)
    headings = soup.find_all(["h1", "h2", "h3", "h4"])
    for heading in headings:
        next_tag = heading.find_next_sibling()
        if next_tag and next_tag.name in ["p", "div", "li", "span"]:
            q = heading.get_text(strip=True)
            a = next_tag.get_text(strip=True)
            if q.endswith("?") and a:
                faqs.append({"question": q, "answer": a})

    if faqs:
        return faqs

    # 4. Fallback to a broader search (from app.py)
    texts = [t.get_text(" ", strip=True) for t in soup.find_all(["p", "div", "li", "span", "h2", "h3", "h4", "strong", "b"])]
    
    questions = []
    answers = []
    
    for i in range(len(texts) - 1):
        if (texts[i].startswith("Q") or texts[i].endswith("?")) and texts[i+1].startswith("A"):
            questions.append(texts[i])
            answers.append(texts[i+1])
    
    for q, a in zip(questions, answers):
        faqs.append({"question": q, "answer": a})
        
    return faqs

def fetch_and_extract_all(url: str) -> list:
    """Fetches the HTML using a tiered approach and extracts FAQs."""
    html = ""
    faqs = []
    
    # Try the fastest method first (requests)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        html = response.text
        faqs = extract_faqs_from_html(html)
        if faqs:
            return faqs
    except Exception as e:
        st.error(f"[!] Requests failed: {e}. Attempting fallback...")

    # Fallback 1: requests_html for JavaScript rendering
    if not faqs and HTMLSession:
        st.info("Falling back to requests_html for JS rendering...")
        try:
            session = HTMLSession()
            r = session.get(url)
            r.html.render(timeout=20, sleep=5)
            html = r.html.html
            faqs = extract_faqs_from_html(html)
            if faqs:
                return faqs
        except Exception as e:
            st.error(f"[!] requests_html failed: {e}. Attempting final fallback...")
    
    # Final Fallback: Selenium for full browser automation
    if not faqs:
        st.info("Falling back to Selenium for full browser automation...")
        try:
            html = get_page_source_selenium(url)
            faqs = extract_faqs_from_html(html)
            return faqs
        except Exception as e:
            st.error(f"[!] Selenium failed: {e}.")
            return []

    return faqs

# --- Caching and Storage ---

def load_faq_cache():
    """Loads FAQs from the cache file."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_faq_cache(faq_store):
    """Saves the FAQ cache to a file."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(faq_store, f, ensure_ascii=False, indent=2)

# --- Streamlit UI ---

st.title("Unified FAQ Extractor")

faq_store = load_faq_cache()

url = st.text_input("Enter a URL:")

if st.button("Extract FAQs"):
    if url:
        start_time = time.time()
        
        # Check cache first
        if url in faq_store:
            st.info("Loaded FAQs from cache ")
            faqs = faq_store[url]
        else:
            with st.spinner("Extracting FAQs... Please wait"):
                faqs = fetch_and_extract_all(url)
                if faqs:
                    faq_store[url] = faqs
                    save_faq_cache(faq_store)

        end_time = time.time()
        exec_time = end_time - start_time
        
        if faqs:
            st.success(f"Successfully extracted {len(faqs)} FAQs!")
            st.info(f"⏱ Execution Time: {exec_time:.2f} seconds")
            
            # Display FAQs
            for idx, qa in enumerate(faqs, 1):
                with st.expander(f"Q{idx}: {qa['question']}"):
                    st.write(f"**Answer:** {qa['answer']}")
            
            # Download buttons
            json_file = json.dumps(faqs, indent=2, ensure_ascii=False)
            st.download_button(
                label="Download FAQs as JSON",
                data=json_file,
                file_name="faqs.json",
                mime="application/json"
            )
            
            jsonl_lines = "\n".join([json.dumps({"messages": [{"role": "user", "content": faq["question"]}, {"role": "assistant", "content": faq["answer"]}]}) for faq in faqs])
            st.download_button(
                label="Download FAQs as JSONL",
                data=jsonl_lines,
                file_name="faqs.jsonl",
                mime="application/jsonl"
            )
        else:
            st.warning("No FAQs could be extracted from this URL.")