# 🕸️ Web Scraper & Data Extractor

A safe, reproducible web scraper with AI-powered CSS selector detection using Google Gemini.

## Features

- 📥 Accept URLs or HTML files
- 🧠 Auto-detect CSS selectors with Gemini AI (optional)
- ⚙️ Manual selector override
- 💾 SQLite snapshot storage for reproducibility
- 📤 Export to JSON / CSV

## Installation

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd <your-repo-name>
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

Create a `.env` file:
```bash
GEMINI_API_KEY=your_api_key_here
```

Get your API key at: https://aistudio.google.com/app/apikey

## Usage

### Generate sample data
```bash
python snapshot_generator.py
```

### Run the app
```bash
streamlit run app.py
```

## Project Structure
.
├── app.py                    # Main Streamlit application
├── extractor.py              # Core extraction logic
├── snapshot_generator.py     # Generate sample HTML files
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (create this)
├── .gitignore               # Git ignore rules
├── snapshots/               # HTML snapshots (auto-created)
└── snapshots.db             # SQLite database (auto-created)

## How It Works

1. **Input**: Provide URLs, upload HTML files, or select saved snapshots
2. **Extract**: Use Gemini AI, manual selectors, or heuristics
3. **Store**: Save snapshots to SQLite for reproducibility
4. **Export**: Download results as JSON or CSV

## API Key Setup

The new Google Gemini SDK (`google-genai`) requires an API key:

1. Visit https://aistudio.google.com/app/apikey
2. Create an API key
3. Add it to your `.env` file

## Notes

- Always check `robots.txt` before scraping
- Respect website Terms of Service
- Use snapshots for reproducible results
- Add rate limiting for production use

## License

MIT License
📋 Installation Instructions

Save all files with the exact names shown above
Create .env file with your Gemini API key
Install dependencies:

pip install -r requirements.txt

Test it:

python snapshot_generator.py
   streamlit run app.py