from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
import cloudscraper
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Vibe Digest API")

# Configure CORS
origins = [
    "http://localhost:3000",
    "https://vibe-digest.vercel.app",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SummarizeRequest(BaseModel):
    url: str

@app.post("/api/summarize")
async def summarize(request: SummarizeRequest):
    # 1. Extract content using cloudscraper (Primary)
    content = ""
    error_details = []
    
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        response = scraper.get(request.url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header", "iframe", "noscript"]):
            script.decompose()
        content = soup.get_text(separator=' ', strip=True)
        
    except Exception as e:
        error_details.append(f"Cloudscraper failed: {str(e)}")
        
        # 2. Fallback: Google Web Cache (Bypass IP blocking)
        try:
            print(f"Primary scraping failed. Trying Google Web Cache for {request.url}")
            # Use specific headers to mimic a user coming from Google Search
            cache_url = f"http://webcache.googleusercontent.com/search?q=cache:{request.url}&strip=1&vwsrc=0"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://www.google.com/"
            }
            response = requests.get(cache_url, headers=headers, timeout=10)
            
            # Google Cache returns 404 if not found, or 200 if found
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Google Cache adds a header/banner, remove it
                auth_header = soup.find(id="google-cache-hdr")
                if auth_header:
                    auth_header.decompose()
                    
                content = soup.get_text(separator=' ', strip=True)
            else:
                error_details.append(f"Google Cache returned {response.status_code}")
                
        except Exception as e2:
            error_details.append(f"Google Cache failed: {str(e2)}")

    if not content:
        # If all methods fail, raise the accumulated errors
        raise HTTPException(status_code=500, detail=f"Failed to fetch content. Errors: {'; '.join(error_details)}")

    # 2. Summarize with Google Gemini
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
         raise HTTPException(status_code=500, detail="Gemini API Key not configured")
    
    try:
        genai.configure(api_key=gemini_key)
        
        # Dynamic Model Selection: Find a model that supports generateContent
        # This fixes persistent 404 errors by asking the API "what can I use?"
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except Exception as e:
            print(f"Error listing models: {e}")

        # Priority list
        target_model = 'models/gemini-1.5-flash' # Default
        
        # Try to match the best available model
        priorities = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro', 'gemini-pro']
        
        found_model = None
        for p in priorities:
            for m in available_models:
                if p in m:
                    found_model = m
                    break
            if found_model:
                break
        
        if found_model:
            target_model = found_model
            print(f"Selected Gemini Model: {target_model}")
        elif available_models:
            target_model = available_models[0] # Fallback to first available
            print(f"Fallback Gemini Model: {target_model}")
            
        model = genai.GenerativeModel(target_model)
        
        prompt = f"""
        Please summarize the following content. The summary must be in the language of the content.
        
        Format:
        1. One sentence headline (bold)
        2. 3 Key Points (bullet list)
        3. Insight Comment (italic)
        
        Content:
        {content[:30000]} 
        """
        
        response = model.generate_content(prompt)
        summary = response.text
        return {"summary": summary}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Gemini summarization failed: {str(e)}")
