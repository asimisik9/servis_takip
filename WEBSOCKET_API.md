# WebSocket API Kullanımı

Bu API, otobüslerin anlık konumunu canlı olarak izlemek için WebSocket endpointi sunar.

## WebSocket Endpoint

```
/ws/bus/{bus_id}/location
```

### Açıklama
- Şoför, bu endpoint'e bağlanıp konum verisi gönderir.
- Veli veya izleyici, aynı endpoint'e bağlanarak anlık konum güncellemelerini canlı olarak alır.

### Mesaj Formatı
- **Gönderilen/Gelen JSON:**
  ```json
  {
    "latitude": 39.9334,
    "longitude": 32.8597,
    "timestamp": "2025-10-17T12:34:56"
  }
  ```

### Test
- Swagger arayüzünde görünmez. Test için Postman, Insomnia, browser WebSocket client veya frontend uygulaması kullanabilirsiniz.

### Örnek JavaScript Client
```js
const ws = new WebSocket("ws://localhost:8000/ws/bus/123/location");
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Konum güncellendi:", data);
};
// Konum göndermek için:
ws.onopen = () => {
  ws.send(JSON.stringify({ latitude: 39.9334, longitude: 32.8597, timestamp: new Date().toISOString() }));
};
```
