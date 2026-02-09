from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Vibe Digest API")

# Configure CORS
origins = [
    "http://localhost:3000",
    "https://vibe-digest.vercel.app",  # Add your production domain if known
    "*" # Allow all for development convenience, narrow down later
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
            "X-With-Generated-Alt": "true" # Optional header for better alt text
        }
        # Check if Jina API Key is provided, though optional for free tier
        jina_key = os.getenv("JINA_API_KEY")
        if jina_key:
            headers["Authorization"] = f"Bearer {jina_key}"
            
        response = requests.get(jina_url, headers=headers)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch content from Jina AI: {str(e)}")

    # 2. Summarize with OpenAI GPT-4o-mini
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
         raise HTTPException(status_code=500, detail="OpenAI API Key not configured")
    
    client = OpenAI(api_key=openai_key)
    
    prompt = f"""
    Please summarize the following content. The summary must be in the language of the content.
    
    Format:
    1. One sentence headline (bold)
    2. 3 Key Points (bullet list)
    3. Insight Comment (italic)
    
    Content:
    {content[:15000]} 
    """
    # Truncate to avoid token limits, though 128k context is large, it saves cost/time.

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional content summarizer. Provide concise and actionable summaries."},
                {"role": "user", "content": prompt}
            ]
        )
        summary = completion.choices[0].message.content
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI summarization failed: {str(e)}")
