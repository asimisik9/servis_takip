# Route Optimization Feature Documentation

## Overview
Servis Takip Backend API'sine Google Maps API kullanarak **en kısa rota hesaplama** özelliği eklendi. Bu özellik, her servis aracında bulunan öğrencilerin adreslerine göre en uygun rotayı hesaplar.

## Features
- **Optimize Route Calculation**: Google Maps Directions API ile waypoint optimizasyonu
- **Smart Geocoding**: Öğrenci adresleri otomatik olarak enlem/boylama çevrilir
- **Route Caching**: Rotalar 30 dakika boyunca Redis'te cache'lenir
- **Cache Invalidation**: Öğrenci atama/adresleri güncellendiğinde otomatik invalidate
- **Error Handling**: Google Maps API hataları sorunsuzca işlenir, fallback rotası döner

## Implementation Details

### New Files Created

#### 1. `app/services/route_service.py`
Ana rota optimizasyon servisi

**Key Methods:**
- `get_optimized_route(bus_id)` - Servis için optimize edilmiş rotayı getirir
- `_get_student_stops(bus_id)` - Atanan öğrencilerin koordinatlarını alır
- `_optimize_with_google_maps(bus_id, stops)` - Google Maps API ile optimizasyon yapar
- `invalidate_route_cache(bus_id)` - Belirli servisin cache'ini temizler
- `invalidate_all_routes_cache()` - Tüm cache'i temizler

#### 2. `app/database/schemas/route.py`
Request/Response modelleri

**Schemas:**
```python
class RouteStop:
    student_id: str
    full_name: str
    student_number: str
    address: str
    latitude: float
    longitude: float
    sequence_order: int  # Optimize edilmiş sıra

class OptimizedRouteResponse:
    bus_id: str
    stops: List[RouteStop]
    total_distance_meters: int
    total_duration_seconds: int
    generated_at: datetime
```

### Modified Files

#### 1. `app/core/redis.py`
Redis manager'a helper metodlar eklendi:
- `get(key)` - Değer getir
- `set(key, value, ex)` - Değer kaydet (expiration ile)
- `delete(key)` - Değer sil
- `delete_pattern(pattern)` - Pattern'e uygun tüm değerleri sil

#### 2. `app/routers/driver.py`
Yeni endpoint:
```http
GET /api/driver/buses/me/route
```
- Şoförün sorumlu olduğu servis için optimize edilmiş rotayı döner
- Erişim: Sadece "sofor" role'üne sahip kullanıcılar

#### 3. `app/routers/admin/buses.py`
Yeni endpoint:
```http
GET /api/admin/buses/{bus_id}/route
```
- Admin tarafından belirli bir servis için rotayı görüntüleyebilir
- Erişim: Sadece "admin" role'üne sahip kullanıcılar

#### 4. `app/services/driver_service.py`
Yeni method:
- `get_driver_bus_id(driver_id)` - Şoförün servis ID'sini getirir

#### 5. `app/services/assignment_service.py`
Cache invalidation eklendi:
- Öğrenci bus atama yapılırken
- Öğrenci bus atama silinirken

#### 6. `app/services/student_service.py`
Cache invalidation eklendi:
- Öğrenci adresi güncellenirken
- Address geocoding otomatik çalışıyor zaten

#### 7. `.env.example`
Yeni configuration:
```bash
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
REDIS_HOST=redis
REDIS_PORT=6379
```

## Setup Instructions

### 1. Environment Configuration
`.env` dosyasında aşağıdaları konfigüre edin:

```bash
# Google Maps API Key (Directions API ve Geocoding API etkin olmalı)
GOOGLE_MAPS_API_KEY=your_actual_api_key

# Redis Configuration (zaten kurulu olmalı)
REDIS_HOST=redis    # Docker containerda
REDIS_PORT=6379
```

### 2. Google Maps API Setup
1. [Google Cloud Console](https://console.cloud.google.com) açın
2. Yeni proje oluşturun veya mevcut projeyi seçin
3. Aşağıdaki API'leri etkinleştirin:
   - **Directions API** - Rota hesaplama için
   - **Geocoding API** - Adres → Koordinat dönüşümü için
4. Billing account bağlayın
5. API Key oluşturun (Application Restrictions: HTTP referrers)
6. `.env`'ye kopyalayın

### 3. Docker Compose
Redis servisi `docker-compose.yml`'de zaten tanımlanmış olmalıdır:
```yaml
redis:
  image: redis:alpine
  ports:
    - "6379:6379"
```

### 4. Requirements.txt Check
Gerekli paketler requirements.txt'de bulunmalıdır:
- `googlemaps>=4.10.0` ✓
- `redis>=5.2.0` ✓

## API Usage Examples

### Get Optimized Route for Driver's Bus
```bash
curl -X GET "http://localhost:8001/api/driver/buses/me/route" \
  -H "Authorization: Bearer YOUR_DRIVER_TOKEN"
```

**Response (200 OK):**
```json
{
  "bus_id": "550e8400-e29b-41d4-a716-446655440000",
  "stops": [
    {
      "student_id": "123e4567-e89b-12d3-a456-426614174000",
      "full_name": "Ahmet Yılmaz",
      "student_number": "2024001",
      "address": "Ankara, Keçiören, Atatürk Blv. No: 45",
      "latitude": 39.9334,
      "longitude": 35.0856,
      "sequence_order": 1
    },
    {
      "student_id": "223e4567-e89b-12d3-a456-426614174001",
      "full_name": "Fatma Demir",
      "student_number": "2024002",
      "address": "Ankara, Çankaya, Tunalı Blv. No: 120",
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

### Get Route for Specific Bus (Admin)
```bash
curl -X GET "http://localhost:8001/api/admin/buses/550e8400-e29b-41d4-a716-446655440000/route" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

## Error Handling

### Scenarios

1. **Bus Not Found**
   - Status: 404
   - Response: `{"detail": "Bus not found: {bus_id}"}`

2. **No Students Assigned**
   - Status: 200
   - Response: Empty stops array
   ```json
   {
     "bus_id": "...",
     "stops": [],
     "total_distance_meters": 0,
     "total_duration_seconds": 0,
     "generated_at": "..."
   }
   ```

3. **Missing Coordinates**
   - Öğrenciler warning log'u alır, rota hesaplamasından hariç tutulur
   - Log: `"Student {id} ({name}) has no coordinates, skipping from route"`

4. **Google Maps API Error**
   - Fallback: Unoptimized route döner (stops sırası değişmez)
   - Log: `"Google Maps API error: {error}"`
   - Cache'e kaydedilmez

5. **Single Student (< 2 stops)**
   - Optimization yapılmaz
   - Stops sırası korunur
   - Distance ve duration: 0

## Caching Strategy

### Cache Keys
- Format: `route:{bus_id}`
- TTL: 1800 seconds (30 minutes)

### Invalidation Triggers
1. **Student Bus Assignment** - Oluşturulurken
2. **Student Bus Assignment** - Silinirken
3. **Student Address Update** - Adres değiştiğinde
4. **Student Address Geocoding** - Koordinatlar değiştiğinde

### Cache Hit
- Redis'te geçerli cache varsa döner
- Log: `"Route cache hit for bus {bus_id}"`

## Performance Considerations

### Optimization
- **Waypoint Optimization**: Google Maps optimize_waypoints=True
- **Caching**: 30 dakikalık cache azaltır API çağrılarını
- **Max Stops**: Google Maps 25 waypoint limitine sahiptir (öğrenci sayısı kontrol edin)

### Limits
- Google Maps Directions API: 25 waypoints per request
- Redis cache: memory'ye bağlı
- API Rate Limit: API key'e bağlı

### Scaling
Çok sayıda servis varsa:
1. Cache TTL'i ayarlayın (route_service.py line 101: `ex=1800`)
2. Redis cluster kullanın
3. Google Maps API quotasını yükseltin

## Testing

### Manual Testing

1. **Test Data Kurulumu**
   ```sql
   -- Öğrenciler + adresler oluşturun
   -- Bus oluşturun
   -- Atamalar yapın
   ```

2. **Endpoint Test**
   ```bash
   # Şoför tokeni ile
   curl -X GET "http://localhost:8001/api/driver/buses/me/route" \
     -H "Authorization: Bearer $DRIVER_TOKEN"
   
   # Admin tokeni ile
   curl -X GET "http://localhost:8001/api/admin/buses/{bus_id}/route" \
     -H "Authorization: Bearer $ADMIN_TOKEN"
   ```

3. **Cache Kontrol**
   ```bash
   # Redis'e bağlan
   redis-cli
   
   # Cache key'leri listele
   KEYS route:*
   
   # Belirli cache'i görüntüle
   GET route:{bus_id}
   ```

### Unit Tests
Test dosyaları yazıldığında şunları test edin:
- ✓ Optimize edilmiş rota sırası
- ✓ Total distance/duration hesaplanması
- ✓ Cache hit/miss
- ✓ Google Maps API error handling
- ✓ Missing coordinates handling
- ✓ Single student edge case

## Troubleshooting

### "Google Maps API key not configured"
- `.env` dosyasında `GOOGLE_MAPS_API_KEY` set mi?
- Docker container environment'ında load mi ediliyor?

### "Route cache hit but empty"
- Redis'te corrupt cache olabilir
- `redis-cli FLUSHDB` ile temizle
- Yeniden request et

### "Total distance is 0"
- API error olup fallback route döndü
- Logs'ta "Google Maps API error" mesajı kontrol et
- API key quota'sını kontrol et

### "Students missing from route"
- Geocoding başarısız oldu (adres format'ı yanlış)
- Student address field'ı null
- Logs'ta warning message'lar kontrol et

## Security Considerations

1. **API Key Security**
   - `.env` dosyası production'da güvenli tutulmalı
   - API Key'e Application Restrictions konulmalı
   - HTTP referrers ile sınırlandırılmalı

2. **Rate Limiting**
   - Google Maps API quota'sı set edin
   - Cache kullanarak API çağrılarını azaltın

3. **Authorization**
   - Şoför sadece kendi bus'ının rotasını görebilir
   - Admin tüm bus'ları görebilir

## Future Enhancements

1. **Real-time Route Updates**
   - WebSocket ile dinamik rota güncellemeleri
   
2. **Alternative Routes**
   - Multiple optimal routes döndürme
   - Alternative seçenekler gösterme

3. **Time Windows**
   - Belirli saatlerde öğrenci pickup/dropoff
   - Schedule-based optimization

4. **Vehicle Constraints**
   - Kapasite kontrolleri
   - Multiple vehicles optimization

5. **Historical Analysis**
   - Rota verileri veritabanında sakla
   - Analytics dashboard

## Production Checklist

- [ ] Google Maps API key set ve test
- [ ] Redis configured ve running
- [ ] Requirements.txt updated
- [ ] .env.example documentation
- [ ] Error logging configured
- [ ] Cache invalidation working
- [ ] Load test (kaç öğrenci safe?)
- [ ] Security audit (API key protection)
- [ ] Monitoring setup (API usage, cache hits)
- [ ] Documentation complete
