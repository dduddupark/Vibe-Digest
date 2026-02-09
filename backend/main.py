from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
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
    # 1. Extract content with Jina AI Reader
    jina_url = f"https://r.jina.ai/{request.url}"
    try:
        headers = {
            "X-With-Generated-Alt": "true"
        }
        jina_key = os.getenv("JINA_API_KEY")
        if jina_key and jina_key.strip() and not jina_key.startswith("...") and "선택사항" not in jina_key:
            headers["Authorization"] = f"Bearer {jina_key}"
            
        response = requests.get(jina_url, headers=headers)
        
        # Retry logic: If 401 Unauthorized, try again without the key (free tier)
        if response.status_code == 401 and "Authorization" in headers:
            print("Jina AI 401 Unauthorized with key. Retrying without key...")
            del headers["Authorization"]
            response = requests.get(jina_url, headers=headers)

        response.raise_for_status()
        content = response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch content from Jina AI ({response.status_code if 'response' in locals() else 'Unknown'}): {str(e)}")

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
