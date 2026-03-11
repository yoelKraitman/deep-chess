import google.generativeai as genai

# Put your API Key here
genai.configure(api_key="YOUR_API_KEY_HERE")

print("Searching for available models...")

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"Available model: {m.name}")
except Exception as e:
    print(f"Error accessing the API: {e}")