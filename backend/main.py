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
        
        # Try known working model patterns in order of preference
        # We use trial-and-error because list_models() is unreliable across API versions
        model_candidates = [
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash",
            "gemini-1.5-flash-001",
            "gemini-1.5-flash-002",
            "gemini-pro",
            "gemini-1.5-pro-latest",
            "gemini-1.5-pro",
        ]
        
        # Optionally try to get available models for logging
        try:
            available = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available.append(m.name)
            print(f"Available models from API: {available}")
            
            # If we got models, prioritize gemini-1.5 variants from the list
            gemini_15_models = [m for m in available if "gemini-1.5" in m and "exp" not in m]
            if gemini_15_models:
                # Prepend discovered 1.5 models to our candidates
                model_candidates = gemini_15_models + [m for m in model_candidates if m not in gemini_15_models]
        except Exception as e:
            print(f"Could not list models (will try predefined patterns): {e}")

        print(f"Will try models in order: {model_candidates[:5]}...")

        safe_content = content[:10000]
        last_error = ""

        # Try each model until one works
        for model_name in model_candidates:
            try:
                print(f"Attempting model: {model_name}")
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
                
                response = await asyncio.to_thread(model.generate_content, prompt)
                if response and response.text:
                    print(f"✅ Success with model: {model_name}")
                    return {"summary": response.text}
            except Exception as e:
                last_error = str(e)
                error_msg = str(e)[:100]
                print(f"❌ Model {model_name} failed: {error_msg}")
                
                # Skip to next model
                continue

        raise HTTPException(status_code=500, detail=f"모든 Gemini 모델 시도 실패. 마지막 에러: {last_error[:200]}")

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"요약 프로세스 중 오류 발생: {str(e)}")
