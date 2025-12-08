# Route Optimization - Quick Start Guide

## 5 Adımda Başlayın

### Adım 1: Google Maps API Key'i Alın

1. https://console.cloud.google.com adresine git
2. Yeni proje oluştur
3. **APIs & Services** → **Enable APIs and Services** git
4. "Directions API" ara ve **Enable** yap
5. "Geocoding API" ara ve **Enable** yap
6. **Credentials** → **Create Credentials** → **API Key**
7. Key'i kopyala

### Adım 2: Environment Konfigürasyonu

`.env` dosyanı güncelle:

```bash
# Mevcut .env dosyasını aç ve aşağıdı ekle:

# Google Maps API (Yukarıda aldığın key)
GOOGLE_MAPS_API_KEY=AIzaSyDxxxxxxxxxxxxxxxxxxxxxx

# Redis (Docker compose'da zaten tanımlanmış)
REDIS_HOST=redis
REDIS_PORT=6379
```

### Adım 3: Docker Redis'i Başlat

```bash
cd /Users/asimisik/development/backend_python/servis_takip

# Redis başlat
docker-compose up redis -d

# Check
docker-compose ps
```

### Adım 4: Backend'i Çalıştır

```bash
# Terminalda
cd /Users/asimisik/development/backend_python/servis_takip

# Virtual environment (zaten aktif mi?)
source .venv/bin/activate

# Server başlat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Server başlatılırken şunu görmeli:
```
INFO:     Uvicorn running on http://0.0.0.0:8001
INFO:     Application startup complete
```

### Adım 5: API'yi Test Et

#### Option A: Şoför Rotası (Kendi Servisi)

```bash
# Şoför token'ı ile (Postman veya curl)
curl -X GET "http://localhost:8001/api/driver/buses/me/route" \
  -H "Authorization: Bearer YOUR_DRIVER_TOKEN" \
  -H "Content-Type: application/json"
```

#### Option B: Admin Rotası (Belirli Servis)

```bash
# Admin token'ı ile
curl -X GET "http://localhost:8001/api/admin/buses/{BUS_ID}/route" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response:**
```json
{
  "bus_id": "550e8400-e29b-41d4-a716-446655440000",
  "stops": [
    {
      "student_id": "123e4567-e89b-12d3-a456-426614174000",
      "full_name": "Ahmet Yılmaz",
      "student_number": "2024001",
      "address": "Ankara, Keçiören",
      "latitude": 39.9334,
      "longitude": 35.0856,
      "sequence_order": 1
    },
    {
      "student_id": "223e4567-e89b-12d3-a456-426614174001",
      "full_name": "Fatma Demir",
      "student_number": "2024002",
      "address": "Ankara, Çankaya",
      "latitude": 39.9108,
      "longitude": 32.8541,
      "sequence_order": 2
    }
  ],
  "total_distance_meters": 15400,
  "total_duration_seconds": 720,
  "generated_at": "2024-12-08T10:30:45.123456"
}
```

## Sorunlar & Çözümler

### ❌ "Google Maps API key not configured"
**Çözüm:**
```bash
# .env dosya kontrol et
cat .env | grep GOOGLE_MAPS_API_KEY

# Yoksa ekle
echo 'GOOGLE_MAPS_API_KEY=YOUR_KEY_HERE' >> .env

# Server'ı restart et
```

### ❌ "No students assigned to bus"
**Status 200, stops: []**
- Veritabanında öğrenci atama yok
- Admin panel veya API ile öğrenci ata

### ❌ "Redis connection refused"
**Çözüm:**
```bash
# Redis running mi?
docker-compose ps

# Değilse başlat
docker-compose up redis -d

# Test
redis-cli ping
# PONG dönmeli
```

### ❌ "Student has no coordinates"
**Warning Log:**
```
Student {id} ({name}) has no coordinates, skipping from route
```
**Çözüm:**
- Admin panel'de öğrenci adresini düzenle (address field)
- Geocoding otomatik coordinate'leri doldur
- Yeniden rota isteme

## Nasıl Çalışıyor?

```
Request (Şoför/Admin)
    ↓
Route Service
    ├─ Cache kontrol (Redis)
    │   ├─ Hit → Cache'den döner ✓
    │   └─ Miss → Google Maps API çağırır
    │
    ├─ Öğrencileri getir (DB)
    ├─ Koordinatları kontrol
    ├─ Google Maps Directions API çağırır
    │   └─ Waypoint Optimization yapır
    ├─ Optimize rotayı sırala
    ├─ Cache'e kaydet (30 dakika)
    └─ Response döner

Response → Client
    └─ Şoför/Admin rota görebilir
```

## Cache Yönetimi

### Cache Durumunu Kontrol Et

```bash
# Redis'e bağlan
redis-cli

# Tüm rota cache'lerini gör
KEYS route:*

# Belirli cache boyutunu kontrol
GET route:{BUS_ID}

# Cache temizle
DEL route:{BUS_ID}

# Tüm route cache'lerini temizle
EVAL "return redis.call('del', unpack(redis.call('keys', 'route:*')))" 0
```

### Cache Otomatik Invalidation

Cache aşağıdaki durumlarda **otomatik** silinir:
- ✓ Öğrenci bus'a atandığında
- ✓ Öğrenci bus'tan kaldırıldığında  
- ✓ Öğrenci adresi güncellendiğinde

## Performance Tips

### 1. Cache Hit Rate'i İzle
```bash
# Logs'ta bak
grep "Route cache hit" logs.txt
grep "Route cache miss" logs.txt
```

### 2. Google Maps API Usage
```
Her şoför/admin rota istiğinde:
- İlk kez: Google Maps API çağrılır (₹)
- Sonraki 30 dakika: Cache'den (Ücretsiz)
```

### 3. Optimize Maliyeti
```
10 öğrenci = 1 API çağrı (25 waypoint limit)
Günde 100 şoför = 100 API çağrı (ilk kez)
= İlk gün biraz, sonrası cache'den = Ucuz ✓
```

## Monitoring

### Log'ları Takip Et

```bash
# Terminal'de server çalışırken
# Aşağıdaki gibi mesajları göreceksin:

# Cache hit
"Route cache hit for bus 550e8400-e29b-41d4-a716-446655440000"

# Optimization başarılı
"Route optimized for bus 550e8400-e29b-41d4-a716-446655440000: 8 stops, distance: 24567m, duration: 1234s"

# Warning (eksik koordinat)
"Student {id} ({name}) has no coordinates, skipping from route"

# Error
"Google Maps API error: INVALID_REQUEST"
```

## Next Steps

1. **Frontend Integration**
   - Admin panel'de route görüntüle
   - Harita üzerinde stops göster
   - Navigation göster

2. **Mobile App Integration**
   - Şoför app'inde rotayı göster
   - Turn-by-turn navigation

3. **Analytics**
   - Rota optimizasyon kazançlarını ölç
   - Zaman/yakıt tasarrufu hesapla

## Support

Sorular veya sorunlar için:
1. Logs'ları kontrol et
2. `.env` configuration'ı doğrula
3. Redis connection test et
4. Google Maps API key validity kontrol et
