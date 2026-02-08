# Backend Production Roadmap

> Son güncelleme: 2025-02-06  
> Hedef: 1000 veli, 70 şoför, 10 admin paneli destekleyen production-ready backend

---

## P0 — Güvenlik (Security) ✅

| # | Sorun | Dosya | Durum |
|---|-------|-------|-------|
| 0.1 | `.gitignore` düzeltildi — `.env`, `firebase-service-account.json`, `google-services.json` eklendi | `.gitignore` | ✅ |
| 0.2 | CORS `settings.BACKEND_CORS_ORIGINS` kullanıyor, dev'de `*` fallback | `app/main.py` | ✅ |
| 0.3 | Access/refresh token ayrı secret + `type` claim eklendi | `app/core/security.py` | ✅ |
| 0.4 | Token blacklist Redis'e taşındı (O(1) lookup), DB sorgusu kaldırıldı | `app/dependencies.py`, `app/services/auth_service.py` | ✅ |

## P1 — Kritik Bug'lar ✅

| # | Sorun | Dosya | Durum |
|---|-------|-------|-------|
| 1.1 | Duplicate `AssignmentService` temizlendi — cache invalidation geri kazanıldı | `app/services/assignment_service.py` | ✅ |
| 1.2 | `AttendanceLog.timestamp` → `AttendanceLog.log_time` düzeltildi | `app/services/attendance_service.py` | ✅ |
| 1.3 | Aynı fix parent_service'de | `app/services/parent_service.py` | ✅ |
| 1.4 | Admin role check → `get_current_admin_user` dependency kullanılıyor | `app/routers/notification.py` | ✅ |
| 1.5 | `BusLocation.speed` nullable yapıldı, schema güncellendi | `bus_location.py`, schema | ✅ |
| 1.6 | `report_absence()` gerçek Absence modeli ile implemente edildi | `parent_service.py`, `absence.py` | ✅ |

## P2 — Performans ✅

| # | Sorun | Dosya | Durum |
|---|-------|-------|-------|
| 2.1 | Redis `KEYS` → `scan_iter` (non-blocking) | `app/core/redis.py` | ✅ |
| 2.2 | 10 DB index eklendi (Alembic migration) | `alembic/versions/a7b8c9d0e1f2_...py` | ✅ |
| 2.3 | `bus_locations` cleanup task oluşturuldu (7 gün retention) | `app/tasks/cleanup_bus_locations.py` | ✅ |
| 2.4 | Senkron `googlemaps.Client` → async `httpx` geocoding | `school_service.py`, `student_service.py` | ✅ |
| 2.5 | `googlemaps` kütüphanesi requirements'tan çıkarıldı | `requirements.txt` | ✅ |

## P3 — Production Altyapı ✅

| # | Sorun | Dosya | Durum |
|---|-------|-------|-------|
| 3.1 | Gunicorn + 4 uvicorn worker, healthcheck eklendi | `Dockerfile` | ✅ |
| 3.2 | Python 3.12 her iki Dockerfile'da | `Dockerfile` | ✅ |
| 3.3 | `.dockerignore` oluşturuldu — secrets image'a girmez | `.dockerignore` | ✅ |
| 3.4 | `docker-compose.yml`: health checks, internal-only ports, Redis maxmemory | `docker-compose.yml` | ✅ |
| 3.5 | Tüm `print()` → `logger` ile değiştirildi | `database.py`, `redis.py`, `security.py` | ✅ |
| 3.6 | Tüm `datetime.utcnow()` → `datetime.now(timezone.utc)` | 6 dosya | ✅ |
| 3.7 | WebSocket `db_error.log` dosya yazma kaldırıldı, task referansları düzeltildi | `location_ws.py` | ✅ |

---

## Sonraki Adımlar

- [x] `alembic upgrade head` çalıştırıldı — tüm migration'lar uygulandı (12 index, absences tablosu, FCM kolonları)
- [x] `bus_locations` cleanup task periyodik olarak çalışıyor (her 6 saat, app lifespan'da asyncio task)
- [x] `.env.example` dosyası `REFRESH_SECRET_KEY` ile güncellendi
- [x] `.env.backend` (Docker dev env) `REFRESH_SECRET_KEY` eklendi
- [x] Alembic migration chain düzeltildi (branch conflict → linear chain)

### Kalan İşler

- [ ] Admin Panel, Veli Mobile, Şoför Mobile düzeltmeleri (ayrı roadmap)
- [ ] Load testing (1000 concurrent WebSocket + API baskısı)
- [ ] APNs sertifikası yükle (bildirimler iOS'ta çalışsın)
- [ ] Production ortamı için ayrı `.env.production` hazırla
- [ ] CI/CD pipeline (GitHub Actions veya benzeri)
