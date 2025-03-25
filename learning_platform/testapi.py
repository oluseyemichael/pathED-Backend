import google.generativeai as genai

genai.configure(api_key="AIzaSyAIFwrnKiI8yOeZX49ahJ00rsJMH1TZVzQ")

try:
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content("Hello, how are you?")
    print(response.text)
except Exception as e:
    print("Error:", e)
