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

    # Task 2: Summarize with Gemini (Direct REST API)
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(status_code=500, detail="Gemini API Key가 설정되지 않았습니다.")
    
    # Use direct REST API to avoid SDK version issues
    async with httpx.AsyncClient() as client:
        # Step 1: Get list of available models
        available_models = []
        for api_version in ["v1", "v1beta"]:
            try:
                list_url = f"https://generativelanguage.googleapis.com/{api_version}/models"
                response = await client.get(list_url, params={"key": gemini_key}, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    for m in models:
                        model_name = m.get("name", "")
                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" in methods:
                            available_models.append((api_version, model_name))
                            print(f"✓ Found: {api_version}/{model_name}")
                    break  # Use first working API version
            except Exception as e:
                print(f"⚠️ Failed to list models on {api_version}: {str(e)[:100]}")
                continue
        
        # Step 2: Filter and prioritize models
        if not available_models:
            print("⚠️ Could not discover models, using fallback list")
            # Fallback: try common model names with both API versions
            available_models = [
                ("v1", "models/gemini-1.5-flash-latest"),
                ("v1", "models/gemini-1.5-flash"),
                ("v1beta", "models/gemini-1.5-flash-latest"),
                ("v1beta", "models/gemini-1.5-flash"),
            ]
        
        # Prioritize gemini-1.5-flash variants
        prioritized = []
        for api_ver, model in available_models:
            if "gemini-1.5" in model and "flash" in model and "exp" not in model.lower():
                prioritized.insert(0, (api_ver, model))
            else:
                prioritized.append((api_ver, model))
        
        print(f"📋 Will try {len(prioritized[:5])} models: {[m for _,m in prioritized[:5]]}")
        
        # Step 3: Try models
        safe_content = content[:10000]
        prompt = f"""
Please provide a highly structured summary of the following article in Korean.

Strictly follow this format:
1. One sentence headline starting with **[Headline]**
2. 3 Key Points as a bulleted list
3. One Insight Comment starting with *[Insight]* and in italics

Article content:
{safe_content}
"""
        
        last_error = ""
        
        for api_version, full_model_name in prioritized[:10]:  # Try up to 10 models
            try:
                # Extract model name (remove 'models/' prefix if present)
                model_name = full_model_name.replace("models/", "")
                
                url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model_name}:generateContent"
                
                payload = {
                    "contents": [{
                        "parts": [{
                            "text": prompt
                        }]
                    }]
                }
                
                print(f"🔄 Trying {api_version}/{model_name}...")
                
                response = await client.post(
                    url,
                    params={"key": gemini_key},
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract text from response
                    try:
                        summary = data["candidates"][0]["content"]["parts"][0]["text"]
                        print(f"✅ SUCCESS with {api_version}/{model_name}")
                        return {"summary": summary}
                    except (KeyError, IndexError) as e:
                        print(f"⚠️ Response format error: {e}")
                        print(f"Response structure: {list(data.keys())}")
                        continue
                else:
                    error_text = response.text[:300]
                    print(f"❌ {api_version}/{model_name}: HTTP {response.status_code}")
                    print(f"   Error: {error_text}")
                    last_error = f"{response.status_code}: {error_text}"
                    
            except Exception as e:
                error_msg = str(e)[:150]
                print(f"❌ {api_version}/{model_name}: Exception - {error_msg}")
                last_error = str(e)
                continue
        
        raise HTTPException(
            status_code=500, 
            detail=f"모든 Gemini API 호출 실패 ({len(prioritized)} 모델 시도). 마지막 에러: {last_error[:200]}"
        )
