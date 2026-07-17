import google.generativeai as genai
import google.auth


API_KEY = # Paste the key directly here

print(genai.__version__)
genai.configure(api_key=API_KEY)

for m in genai.list_models():
    print(m.name, m.supported_generation_methods)

model = genai.GenerativeModel("gemini-2.0-flash")

response = model.generate_content("Say hello.")
print(response.text)
