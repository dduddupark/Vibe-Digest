from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
from bs4 import BeautifulSoup
from google import genai
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
    # 1. Extract content with Jina AI Reader (Reverted due to 403 blocks)
    jina_url = f"https://r.jina.ai/{request.url}"
    try:
        headers = {
            "X-With-Generated-Alt": "true"
        }
        jina_key = os.getenv("JINA_API_KEY")
        # Strict check: ignore placeholders or empty strings
        if jina_key and len(jina_key) > 10 and not jina_key.startswith("...") and "선택사항" not in jina_key:
            headers["Authorization"] = f"Bearer {jina_key}"
        else:
            print("Jina AI Key is invalid or missing. Using free tier.")
            
        response = requests.get(jina_url, headers=headers)
        
        # Retry logic: If 401 Unauthorized, try again without the key (free tier)
        if response.status_code == 401 and "Authorization" in headers:
            print("Jina AI 401 Unauthorized with key. Retrying without key...")
            del headers["Authorization"]
            response = requests.get(jina_url, headers=headers)

        response.raise_for_status()
        content = response.text
    except Exception as e:
        # Fallback to direct requests if Jina AI fails completely
        try:
            print(f"Jina AI failed ({str(e)}). Trying direct scraping...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(request.url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            content = soup.get_text(separator=' ', strip=True)
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"Failed to fetch content (Jina: {str(e)}, Direct: {str(e2)})")

    # 2. Summarize with Google Gemini
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
         raise HTTPException(status_code=500, detail="Gemini API Key not configured")
    
    try:
        client = genai.Client(api_key=gemini_key)
        
        prompt = f"""
        Please summarize the following content. The summary must be in the language of the content.
        
        Format:
        1. One sentence headline (bold)
        2. 3 Key Points (bullet list)
        3. Insight Comment (italic)
        
        Content:
        {content[:30000]} 
        """
        
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        summary = response.text
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Gemini summarization failed: {str(e)}")
