from fastapi import FastAPI
import uvicorn

# FastAPI uygulamasını oluşturuyoruz
app = FastAPI()

# Ana sayfa (/) için bir GET isteği rotası belirliyoruz
# Flask'taki @app.route('/')'nun modern hali
@app.get("/")
async def ana_sayfa():
    return {"mesaj": "Merhaba FastAPI Dünyası!"}

@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}

# Eğer bu dosya doğrudan çalıştırılırsa, uvicorn'u başlat
# Bu, sadece geliştirme sırasında hızlı test için bir yöntemdir.
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)