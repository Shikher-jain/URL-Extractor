import re
import json
import requests
from bs4 import BeautifulSoup
import os
import streamlit as st

try:
    from requests_html import HTMLSession
except ImportError:
    HTMLSession = None

DATA_FILE = "faqs.jsonl"

def clean_text(text: str) -> str:
    """Clean unwanted symbols and normalize spaces."""
    text = re.sub(r"¶", "", text)
    text = re.sub(r"Â", "", text)
    text = re.sub(r"<\[\d+\]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\xa0", " ", text)
    text = re.sub(r"\[.*?\]", " ", text)
    return text.strip()

def fetch_html(url: str) -> str:
    """Fetch HTML using requests, fallback to JS rendering if needed."""
    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        html = res.text
    except Exception as e:
        st.error(f"[!] Requests failed: {e}")
        html = ""

    # If JS rendering required
    if (("faq" in url.lower()) or not html.strip()) and HTMLSession:
        try:
            session = HTMLSession()
            r = session.get(url)
            r.html.render(timeout=20)
            html = r.html.html
        except Exception as e:
            st.error(f"[!] JS rendering failed: {e}")
    return html

def remove_noise(soup):
    for tag in soup(["head", "script", "style", "nav", "footer", "header",  "form", "noscript", "iframe", "button", "input",  "aside", "svg", "canvas", "link", "meta"]):
        tag.decompose()

    # Common ids/classes for noise removal
    noisy = ["footer","header","nav","toc","sidebar","masthead","menu","cookies","ads","advertisement","promo","newsletter"]
    for nid in noisy:
        for tag in soup.find_all(id=lambda x: x and nid in x.lower()):
            tag.decompose()
        for tag in soup.find_all(class_=lambda x: x and nid in x.lower()):
            tag.decompose()
    return soup

# ----------------- FAQ Extraction -----------------
def extract_faq(url: str):
    html = fetch_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    remove_noise(soup)

    faqs = []
    seen_q, seen_a = set(), set()

    # Mode A: "Q: ... A: ..." pattern in raw text
    text = soup.get_text("\n")
    qa_pairs = re.findall(r"Q[:\-]?\s*(.*?)\n\s*A[:\-]?\s*(.*?)(?=\nQ[:\-]|\Z)", text, flags=re.S | re.I)
    for q, a in qa_pairs:
        q, a = clean_text(q), clean_text(a)
        if q and a and q not in seen_q and a not in seen_a:
            seen_q.add(q); seen_a.add(a)
            faqs.append({"Q": q, "A": a})

    # Mode B: <dl><dt>/<dd>
    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            q, a = clean_text(dt.get_text()), clean_text(dd.get_text())
            if q and a and q not in seen_q and a not in seen_a:
                seen_q.add(q); seen_a.add(a)
                faqs.append({"Q": q, "A": a})

    # Mode C: Headings (<h2>/<h3>/<h4>) + following content
    for heading in soup.find_all(["h2", "h3", "h4"]):
        q = clean_text(heading.get_text())
        if not q or q in seen_q:
            continue
        answer_parts = []
        for sibling in heading.find_next_siblings():
            if sibling.name in ["h2","h3","h4","dt","div"]:
                break
            if sibling.name in ["p","dd","ul","ol"]:
                answer_parts.append(clean_text(sibling.get_text(" ", strip=True)))
        a = " ".join(answer_parts)
        if a and a not in seen_a:
            seen_q.add(q); seen_a.add(a)
            faqs.append({"Q": q, "A": a})

    return faqs

# ----------------- Storage -----------------
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            faq_store = json.load(f)
    except json.JSONDecodeError:
        faq_store = {}
else:
    faq_store = {}

def save_faq_store():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        for key, value in faq_store.items():
            f.write(json.dumps({"url": key, "faqs": value}, ensure_ascii=False) + "\n")

# ----------------- Streamlit UI -----------------
st.title("FAQ Genie (Rule-based Extractor)")

url = st.text_input("Enter URL:")

if url:
    if url in faq_store:
        st.info("Loaded FAQs from cache")
        faqs = faq_store[url]
    else:
        with st.spinner("Extracting FAQs..."):
            faqs = extract_faq(url)
            faq_store[url] = faqs
            save_faq_store()
            st.success(f"Extracted {len(faqs)} FAQs and cached.")

    if faqs:
        with st.expander("View Extracted FAQs"):
            for line in faqs:
                st.json(line)

        question = st.selectbox("Select a question:", options=[line["Q"] for line in faqs])
        if question:
            answer = next((line["A"] for line in faqs if line["Q"] == question), "Not found")
            st.subheader("Answer:")
            st.write(answer)
        
        st.markdown("---")
        st.subheader("Download Options:")

        # Download as generic JSON
        json_output = json.dumps(faqs, indent=2, ensure_ascii=False)
        st.download_button(
            label="Download FAQs as JSON",
            data=json_output,
            file_name="faqs.jsonl",
            mime="application/jsonl"
        )

        # Download as Fine-tuning JSONL
        # This converts the {"Q": q, "A": a} format to {"messages": [{"role": "user", "content": q}, {"role": "assistant", "content": a}]}
        fine_tuning_jsonl_lines = []
        for faq_item in faqs:
            entry = {
                "messages": [
                    {"role": "user", "content": faq_item["Q"]},
                    {"role": "assistant", "content": faq_item["A"]}
                ]
            }
            fine_tuning_jsonl_lines.append(json.dumps(entry, ensure_ascii=False))

        st.download_button(
            label="Download FAQs as JSONL",
            data="\n".join(fine_tuning_jsonl_lines),
            file_name="faqs.jsonl",
        )
