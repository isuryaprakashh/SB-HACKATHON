# extractor.py
import re
import json
import sqlite3
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Dict, Optional, Tuple, Any
from dotenv import load_dotenv
import os

# Load environment variables (Gemini API key, etc.)
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ---------- Regex patterns ----------
CURRENCY_RE = re.compile(r'(\$|€|£|\u20B9)\s?[\d{1,3},]*\d+(\.\d+)?')
NUMBER_RE = re.compile(r'[\d{1,3},]*\d+(\.\d+)?')

# ---------- Fetch HTML ----------
def fetch_html(url: str, timeout=10, headers=None) -> Tuple[str, str]:
    """
    Fetch a web page's HTML content.
    Returns (final_url, html).
    """
    headers = headers or {"User-Agent": "SafeExtractorBot/1.0 (+https://example.com)"}
    r = requests.get(url, timeout=timeout, headers=headers)
    r.raise_for_status()
    return r.url, r.text

# ---------- Snapshot Storage ----------
def snapshot_to_db(db_path: str, url: str, html: str):
    """
    Store HTML snapshot in SQLite for reproducibility.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            domain TEXT,
            fetched_at TEXT,
            html TEXT
        )
    """)
    domain = urlparse(url).netloc
    cur.execute(
        "INSERT INTO snapshots (url, domain, fetched_at, html) VALUES (?, ?, ?, ?)",
        (url, domain, datetime.datetime.utcnow().isoformat(), html)
    )
    conn.commit()
    conn.close()

# ---------- Heuristic Inference ----------
def infer_title(soup: BeautifulSoup) -> Optional[str]:
    for tag in [
        soup.find("meta", property="og:title"),
        soup.find("meta", attrs={"name": "twitter:title"})
    ]:
        if tag and tag.get("content"):
            return tag["content"].strip()

    if soup.title and soup.title.text.strip():
        return soup.title.text.strip()

    for tag_name in ["h1", "h2", "h3"]:
        tag = soup.find(tag_name)
        if tag and tag.text.strip():
            return tag.text.strip()
    return None


def infer_price(soup: BeautifulSoup) -> Optional[str]:
    def has_price_keyword(s): 
        return any(k in s.lower() for k in ["price", "amount", "cost", "sale", "our-price"])

    for tag in soup.find_all(True, attrs={"class": True}):
        cls = " ".join(tag.get("class"))
        if has_price_keyword(cls):
            text = tag.get_text(" ", strip=True)
            if CURRENCY_RE.search(text):
                return CURRENCY_RE.search(text).group(0)

    for tag in soup.find_all(True, attrs={"id": True}):
        ident = tag.get("id")
        if has_price_keyword(ident):
            text = tag.get_text(" ", strip=True)
            if CURRENCY_RE.search(text):
                return CURRENCY_RE.search(text).group(0)

    # fallback
    text = soup.get_text(" ", strip=True)
    m = CURRENCY_RE.search(text)
    if m:
        return m.group(0)

    return None


def infer_availability(soup: BeautifulSoup) -> Optional[str]:
    text = soup.get_text(" ", strip=True).lower()
    for phrase in ["in stock", "out of stock", "available", "pre-order", "preorder"]:
        if phrase in text:
            idx = text.find(phrase)
            return text[max(0, idx - 30): idx + 50].strip()
    return None

# ---------- Apply CSS Selectors ----------
def apply_selectors(soup: BeautifulSoup, mapping: Dict[str, str]) -> Dict[str, Optional[str]]:
    results = {}
    for field, selector in mapping.items():
        if not selector:
            results[field] = None
            continue
        try:
            tag = soup.select_one(selector)
            results[field] = tag.get_text(" ", strip=True) if tag else None
        except Exception:
            results[field] = None
    return results

# ---------- Normalize ----------
def normalize_fields(raw: Dict[str, Optional[str]]) -> Dict[str, Any]:
    price_raw = raw.get("price")
    currency = None
    amount = None
    if price_raw:
        m = CURRENCY_RE.search(price_raw)
        if m:
            currency = m.group(1)
        num_m = NUMBER_RE.search(price_raw)
        if num_m:
            try:
                amount = float(num_m.group(0).replace(",", ""))
            except:
                pass
    return {
        "title": raw.get("title"),
        "price": {
            "raw": price_raw,
            "amount": amount,
            "currency": currency
        },
        "availability": raw.get("availability"),
        "extraction_timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }

# ---------- Main Extractor ----------
def extract_from_html(html: str, mapping: Dict[str, str] = {}) -> Dict[str, Any]:
    """
    mapping: {"title": "h1.title", "price": ".price", "availability": "#stock"}
    If missing, uses heuristic inference.
    """
    soup = BeautifulSoup(html, "lxml")
    selected = apply_selectors(soup, mapping)

    # fallback to heuristics
    if not selected.get("title"):
        selected["title"] = infer_title(soup)
    if not selected.get("price"):
        selected["price"] = infer_price(soup)
    if not selected.get("availability"):
        selected["availability"] = infer_availability(soup)

    return normalize_fields(selected)

# ---------- Gemini-based Selector Inference (NEW SDK) ----------
def llm_infer_selectors(html: str, api_key: str):
    """
    Use Google Gemini to infer CSS selectors for product title, price, and availability.
    Returns a dict like {"title": "h1.product-title", "price": "span.price", "availability": "#stock"}
    """
    if not api_key:
        print("Gemini API key not found in environment (.env).")
        return {}

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("Error: google-genai package not installed. Run: pip install google-genai")
        return {}

    prompt = (
        "You are an expert HTML analyst. Given the following HTML, identify the correct CSS selectors "
        "for three elements: product title, product price, and availability. "
        "Respond ONLY as a JSON object with keys: title, price, availability.\n\n"
        "Example output: {\"title\": \"h1.product-title\", \"price\": \"span.price\", \"availability\": \"#stock\"}\n\n"
        f"HTML:\n{html[:6000]}"
    )

    # List of models to try (newest first)
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]

    errors = {}
    
    for model_name in models_to_try:
        try:
            # Create client with API key
            client = genai.Client(api_key=api_key)
            
            # Generate content with JSON mode
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            # Extract text from response
            text = response.text.strip()
            
            if not text:
                raise ValueError("Empty response from model")
            
            # Clean up any markdown code blocks
            if "```json" in text:
                text = text.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in text:
                text = text.split("```", 1)[1].split("```", 1)[0].strip()
            
            # Parse JSON
            parsed = json.loads(text)
            
            if isinstance(parsed, dict) and any(k in parsed for k in ["title", "price", "availability"]):
                print(f"✅ Successfully used model: {model_name}")
                return parsed
            else:
                raise ValueError("Invalid JSON structure")
                
        except Exception as exc:
            errors[model_name] = str(exc)
            continue

    # If all models failed, log errors
    if errors:
        formatted = "; ".join(f"{name}: {msg}" for name, msg in errors.items())
        print(f"[Gemini inference error] All models failed -> {formatted}")
    
    return {}