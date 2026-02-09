import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY not found in environment variables.")
    exit(1)

try:
    client = genai.Client(api_key=api_key)
    print("Listing available models:")
    # The SDK method to list models might differ, trying common ones
    # specific to the new google-genai SDK
    
    # Based on SDK structure, it might be client.models.list()
    # iterating over it
    for model in client.models.list(config={'page_size': 100}):
        print(f"- {model.name} (Supported methods: {model.supported_generation_methods})")

except Exception as e:
    print(f"Error listing models: {e}")
