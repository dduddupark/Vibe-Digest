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
    # 1. Extract content with multiple fallbacks
    url = request.url.strip()
    content = ""
    error_details = []

    # Source 1: Jina AI with URL Encoding
    try:
        from urllib.parse import quote
        encoded_url = quote(url, safe="")
        jina_url = f"https://r.jina.ai/{url}" # Jina usually handles raw URL well but let's try
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(jina_url, headers=headers, timeout=15)
        if response.status_code == 200:
            potential_content = response.text
            # Basic validation: check if it's not a generic error/help page
            if len(potential_content) > 200 and "Google Search" not in potential_content[:500]:
                content = potential_content
                print("Extracted content via Jina AI")
            else:
                error_details.append("Jina AI returned invalid/help content")
        else:
            error_details.append(f"Jina AI returned status {response.status_code}")
    except Exception as e:
        error_details.append(f"Jina AI failed: {str(e)}")

    # Source 2: Microlink (Powerful backup)
    if not content:
        try:
            print(f"Trying Microlink for {url}")
            microlink_url = f"https://api.microlink.io/?url={quote(url)}&embed=content.text"
            response = requests.get(microlink_url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                content = data.get('data', {}).get('content', {}).get('text', '')
                if content and len(content) > 100:
                    print("Extracted content via Microlink")
                else:
                    content = ""
                    error_details.append("Microlink returned empty content")
            else:
                error_details.append(f"Microlink returned status {response.status_code}")
        except Exception as e:
            error_details.append(f"Microlink failed: {str(e)}")

    # Source 3: Cloudscraper (Last resort direct)
    if not content:
        try:
            print(f"Trying Cloudscraper for {url}")
            scraper = cloudscraper.create_scraper()
            response = scraper.get(url, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for s in soup(["script", "style", "nav", "footer", "header"]):
                    s.decompose()
                content = soup.get_text(separator=' ', strip=True)
                if "Access Denied" in content or "Robot Check" in content:
                    content = ""
                    error_details.append("Cloudscraper hit a block/captcha")
            else:
                error_details.append(f"Cloudscraper returned status {response.status_code}")
        except Exception as e:
            error_details.append(f"Cloudscraper failed: {str(e)}")

    if not content:
        raise HTTPException(status_code=500, detail=f"Failed to fetch content. Errors: {'; '.join(error_details)}")

    # 2. Summarize with Google Gemini (Robust Retry)
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
         raise HTTPException(status_code=500, detail="Gemini API Key not configured")
    
    try:
        genai.configure(api_key=gemini_key)
        
        # Priority models: 1.5-flash is MUCH better for free tier quota (TPM/RPM)
        # Avoid Pro models if possible as they often have 0 quota on new accounts
        models_priority = [
            "models/gemini-1.5-flash",
            "models/gemini-1.5-flash-latest",
            "models/gemini-pro",
            "models/gemini-1.5-pro"
        ]
        
        # Discover actual available models to be sure
        actual_available = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    actual_available.append(m.name)
        except:
            actual_available = models_priority # Fallback to priority list

        # Build final queue: prioritize flash above all
        final_queue = []
        for target in models_priority:
            if target in actual_available:
                final_queue.append(target)
        
        # Add any other available models just in case
        for m in actual_available:
            if m not in final_queue:
                final_queue.append(m)

        if not final_queue:
            final_queue = ["models/gemini-1.5-flash"]

        last_error = ""
        # Truncate content more aggressively to avoid Token-Per-Minute (TPM) limits
        # 10,000 chars is roughly 2.5k-3k tokens, safe for free tier.
        safe_content = content[:10000] 

        for model_name in final_queue:
            try:
                print(f"Summarizing with {model_name}...")
                model = genai.GenerativeModel(model_name)
                prompt = f"""
                Please provide a highly structured summary of the following article in its original language.
                
                Strictly follow this format:
                1. One sentence headline starting with **[Headline]**
                2. 3 Key Points as a bulleted list
                3. One Insight Comment starting with *[Insight]* and in italics
                
                Article content:
                {safe_content}
                """
                response = model.generate_content(prompt)
                if response and response.text:
                    return {"summary": response.text}
            except Exception as e:
                last_error = str(e)
                print(f"Model {model_name} failed: {last_error}")
                # If we get a 429, we skip to the next model (Flash -> Pro etc)
                continue

        raise HTTPException(status_code=500, detail=f"All models reached quota or failed. Last error: {last_error}")

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization process failed: {str(e)}")
