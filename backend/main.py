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

import httpx
import asyncio
from urllib.parse import quote

# Helper functions for parallel fetching
async def fetch_jina(url: str, client: httpx.AsyncClient):
    try:
        jina_url = f"https://r.jina.ai/{quote(url)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        response = await client.get(jina_url, headers=headers, timeout=15)
        if response.status_code == 200 and len(response.text) > 300 and "Google Search" not in response.text[:500]:
            print("Successfully fetched via Jina AI")
            return response.text
    except Exception as e:
        print(f"Jina AI failed: {e}")
    return None

async def fetch_microlink(url: str, client: httpx.AsyncClient):
    try:
        microlink_url = f"https://api.microlink.io/?url={quote(url)}&embed=content.text"
        response = await client.get(microlink_url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            content = data.get('data', {}).get('content', {}).get('text', '')
            if content and len(content) > 150:
                print("Successfully fetched via Microlink")
                return content
    except Exception as e:
        print(f"Microlink failed: {e}")
    return None

async def fetch_google_cache(url: str, client: httpx.AsyncClient):
    try:
        cache_url = f"http://webcache.googleusercontent.com/search?q=cache:{quote(url)}&strip=1&vwsrc=0"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://www.google.com/"
        }
        response = await client.get(cache_url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Remove the cache header
            header = soup.find(id="google-cache-hdr")
            if header: header.decompose()
            content = soup.get_text(separator=' ', strip=True)
            if len(content) > 300 and "Google Search" not in content[:500]:
                print("Successfully fetched via Google Cache")
                return content
    except Exception as e:
        print(f"Google Cache failed: {e}")
    return None

def fetch_cloudscraper_sync(url: str):
    try:
        # Hankyung needs a specific browser fingerprint sometimes
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        response = scraper.get(url, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for s in soup(["script", "style", "nav", "footer", "header", "iframe"]):
                s.decompose()
            content = soup.get_text(separator=' ', strip=True)
            if len(content) > 300 and "Access Denied" not in content:
                print("Successfully fetched via Cloudscraper")
                return content
    except Exception as e:
        print(f"Cloudscraper sync failed: {e}")
    return None

@app.post("/api/summarize")
async def summarize(request: SummarizeRequest):
    url = request.url.strip()
    content = ""
    
    # Task 1: Fetch Content in Quad-Parallel
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Create tasks for all sources
        tasks = [
            fetch_jina(url, client),
            fetch_microlink(url, client),
            fetch_google_cache(url, client),
            asyncio.to_thread(fetch_cloudscraper_sync, url)
        ]
        
        # Wait for all tasks and collect results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Use the first successful (non-None, non-exception) result
        for result in results:
            if result and not isinstance(result, Exception):
                content = result
                print(f"Using content of length: {len(content)}")
                break
    
    if not content:
        raise HTTPException(status_code=500, detail="모든 경로를 통한 기사 읽기에 실패했습니다. URL을 다시 확인해주세요.")

    # Task 2: Summarize with Gemini
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(status_code=500, detail="Gemini API Key가 설정되지 않았습니다.")
    
    try:
        genai.configure(api_key=gemini_key)
        
        # Discover available models
        actual_available = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    actual_available.append(m.name)
                    print(f"Available model: {m.name}")
        except Exception as e:
            print(f"Error listing models: {e}")
            # Fallback to common model names
            actual_available = ["models/gemini-1.5-flash", "models/gemini-pro"]

        # Filter out models with known zero quota (experimental, 3.x versions, etc)
        filtered_models = [
            m for m in actual_available 
            if not any(exclude in m for exclude in ["gemini-3", "gemini-2.5", "exp", "experimental"])
        ]
        
        print(f"Filtered models (excluding zero-quota): {filtered_models}")

        # Priority order: 1.5-flash > 1.5-pro > 1.0-pro
        # We use specific patterns to avoid matching unwanted models
        priorities = [
            ("1.5-flash", "flash"),  # Match 1.5-flash variants
            ("1.5-pro", "1.5-pro"),  # Match 1.5-pro specifically
            ("1.0-pro", "1.0"),      # Match 1.0-pro
        ]
        
        # Build queue by matching priorities with filtered models
        final_queue = []
        for pattern, identifier in priorities:
            for model in filtered_models:
                if pattern in model and model not in final_queue:
                    final_queue.append(model)
                    print(f"Added {model} to queue (matched: {identifier})")
                    break
        
        # If nothing matched, try to find any flash model
        if not final_queue:
            for model in filtered_models:
                if "flash" in model.lower():
                    final_queue.append(model)
                    print(f"Fallback: using flash model {model}")
                    break
        
        # If still nothing, use first filtered model
        if not final_queue and filtered_models:
            final_queue = [filtered_models[0]]
            print(f"Using first available model: {filtered_models[0]}")
        
        # Last resort fallback
        if not final_queue:
            final_queue = ["models/gemini-1.5-flash"]
            print("Using hardcoded fallback: models/gemini-1.5-flash")

        print(f"Final model queue: {final_queue}")

        safe_content = content[:10000]
        last_error = ""

        # Try models
        for model_name in final_queue:
            try:
                print(f"Attempting to use model: {model_name}")
                model = genai.GenerativeModel(model_name)
                prompt = f"""
                Please provide a highly structured summary of the following article in Korean.
                
                Strictly follow this format:
                1. One sentence headline starting with **[Headline]**
                2. 3 Key Points as a bulleted list
                3. One Insight Comment starting with *[Insight]* and in italics
                
                Article content:
                {safe_content}
                """
                # Use async version of generate_content
                response = await asyncio.to_thread(model.generate_content, prompt)
                if response and response.text:
                    print(f"Successfully generated summary with {model_name}")
                    return {"summary": response.text}
            except Exception as e:
                last_error = str(e)
                print(f"Model {model_name} failed: {last_error}")
                continue

        raise HTTPException(status_code=500, detail=f"요약 생성에 실패했습니다. (할당량 초과일 수 있습니다) 마지막 에러: {last_error}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"요약 프로세스 중 오류 발생: {str(e)}")
