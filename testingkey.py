import google.generativeai as genai
import google.auth


API_KEY = "AQ.Ab8RN6Lg57bO1qIJcjgU6CTBO8C0wwC4zsnwjmmzoTWwzffgMQ"      # Paste the key directly here

print(genai.__version__)
genai.configure(api_key=API_KEY)

for m in genai.list_models():
    print(m.name, m.supported_generation_methods)

model = genai.GenerativeModel("gemini-2.0-flash")

response = model.generate_content("Say hello.")
print(response.text)