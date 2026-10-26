import requests

# Запрашиваем актуальный список моделей с сервера OpenRouter
response = requests.get("https://openrouter.ai/api/v1/models")
data = response.json()

print("🔥 АКТУАЛЬНЫЕ БЕСПЛАТНЫЕ МОДЕЛИ ПРЯМО СЕЙЧАС:")
for model in data.get("data", []):
    model_id = model.get("id", "")
    # Проверяем, бесплатная ли модель
    pricing = model.get("pricing", {})
    if ":free" in model_id or (pricing.get("prompt") == "0" and pricing.get("completion") == "0"):
        print(f"👉 {model_id}")
