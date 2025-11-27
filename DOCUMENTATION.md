# Servis Takip Sistemi Backend Dokümantasyonu

Bu doküman, Servis Takip Sistemi backend projesinin tüm işlevlerini, API uç noktalarını ve veri modellerini kapsamaktadır.

## Proje Hakkında

Servis Takip Sistemi, okul servis araçlarının takibi, öğrenci yoklaması ve veli bilgilendirmesi amacıyla geliştirilmiş bir backend servisidir. FastAPI framework'ü kullanılarak geliştirilmiştir ve asenkron bir yapıya sahiptir.

## Temel Özellikler

*   **Kimlik Doğrulama (Authentication):** JWT tabanlı güvenli giriş sistemi.
*   **Rol Yönetimi:** Admin, Şoför ve Veli rolleri.
*   **Gerçek Zamanlı Konum Takibi:** WebSocket ve Redis Pub/Sub ile anlık servis konumu paylaşımı.
*   **Yoklama Sistemi:** Öğrencilerin servise biniş/iniş durumlarının takibi.
*   **Yönetim Paneli API'ları:** Kullanıcı, öğrenci, okul, servis ve atama işlemleri için CRUD operasyonları.

## API Uç Noktaları (Endpoints)

Tüm API uç noktaları `/api/v1` öneki ile başlar (WebSocket hariç).

### 1. Kimlik Doğrulama (Auth)

Kullanıcı kayıt, giriş ve oturum yönetimi işlemleri.

*   **POST** `/api/v1/auth/register`: Yeni kullanıcı kaydı oluşturur.
*   **POST** `/api/v1/auth/login`: Kullanıcı girişi yapar ve Access/Refresh token döndürür. (Rate Limit: 5 istek/dakika)
*   **GET** `/api/v1/auth/me`: Giriş yapmış kullanıcının profil bilgilerini döndürür.
*   **POST** `/api/v1/auth/logout`: Kullanıcı çıkışı yapar ve token'ı geçersiz kılar.
*   **POST** `/api/v1/auth/refresh`: Refresh token kullanarak yeni bir Access token alır.

### 2. Şoför İşlemleri (Driver)

Şoförlerin günlük operasyonlarını yönettiği uç noktalar.

*   **GET** `/api/v1/driver/me/roster`: Şoförün sorumlu olduğu servisteki öğrenci listesini getirir. Opsiyonel olarak tarih filtresi alabilir.
*   **POST** `/api/v1/driver/attendance/log`: Öğrencinin servise bindiğini veya indiğini kaydeder (Yoklama).
*   **POST** `/api/v1/driver/buses/me/location`: Servisin anlık konumunu günceller.

### 3. Veli İşlemleri (Parent)

Velilerin öğrencilerini takip ettiği uç noktalar.

*   **GET** `/api/v1/parent/me/students`: Velinin sistemdeki öğrencilerini listeler.
*   **GET** `/api/v1/parent/students/{student_id}/bus/location`: Seçilen öğrencinin servisinin anlık konumunu getirir.
*   **GET** `/api/v1/parent/students/{student_id}/attendance/history`: Öğrencinin geçmiş yoklama kayıtlarını listeler. Tarih filtresi uygulanabilir.

### 4. Yönetim Paneli (Admin)

Sadece yönetici yetkisine sahip kullanıcıların erişebileceği uç noktalar.

#### Kullanıcı Yönetimi
*   **GET** `/api/v1/admin/users`: Tüm kullanıcıları listeler.
*   **POST** `/api/v1/admin/users`: Yeni kullanıcı oluşturur.
*   **GET** `/api/v1/admin/users/{user_id}`: Belirli bir kullanıcının detaylarını getirir.
*   **PUT** `/api/v1/admin/users/{user_id}`: Kullanıcı bilgilerini günceller.
*   **DELETE** `/api/v1/admin/users/{user_id}`: Kullanıcıyı siler.

#### Öğrenci Yönetimi
*   **GET** `/api/v1/admin/students`: Tüm öğrencileri listeler.
*   **POST** `/api/v1/admin/students`: Yeni öğrenci kaydı oluşturur.
*   **PUT** `/api/v1/admin/students/{student_id}`: Öğrenci bilgilerini günceller.
*   **DELETE** `/api/v1/admin/students/{student_id}`: Öğrenciyi siler.

#### Okul Yönetimi
*   **GET** `/api/v1/admin/schools`: Tüm okulları listeler.
*   **POST** `/api/v1/admin/schools`: Yeni okul ekler.
*   **GET** `/api/v1/admin/schools/{school_id}`: Okul detaylarını getirir.
*   **PUT** `/api/v1/admin/schools/{school_id}`: Okul bilgilerini günceller.
*   **DELETE** `/api/v1/admin/schools/{school_id}`: Okulu siler.

#### Servis Aracı Yönetimi
*   **GET** `/api/v1/admin/buses`: Tüm servis araçlarını listeler.
*   **POST** `/api/v1/admin/buses`: Yeni servis aracı ekler.
*   **PUT** `/api/v1/admin/buses/{bus_id}`: Servis aracı bilgilerini günceller.
*   **DELETE** `/api/v1/admin/buses/{bus_id}`: Servis aracını siler.

#### Atama İşlemleri (Assignments)
*   **POST** `/api/v1/admin/students/{student_id}/assign-parent`: Öğrenciye veli ataması yapar.
*   **POST** `/api/v1/admin/students/{student_id}/assign-bus`: Öğrenciye servis aracı ataması yapar.
*   **POST** `/api/v1/admin/buses/{bus_id}/assign-driver`: Servis aracına şoför ataması yapar.
*   **GET** `/api/v1/admin/assignments/student-bus`: Tüm öğrenci-servis atamalarını listeler.
*   **GET** `/api/v1/admin/assignments/parent-student`: Tüm veli-öğrenci ilişkilerini listeler.
*   **DELETE** `/api/v1/admin/assignments/student-bus/{assignment_id}`: Öğrenci-servis atamasını siler.
*   **DELETE** `/api/v1/admin/assignments/parent-student/{relation_id}`: Veli-öğrenci ilişkisini siler.

#### İzleme ve Raporlama (Monitoring)
*   **GET** `/api/v1/admin/buses/locations`: Tüm aktif servislerin son konumlarını listeler.
*   **GET** `/api/v1/admin/logs/attendance`: Sistemdeki tüm yoklama kayıtlarını filtreleyerek listeler (Tarih, servis, öğrenci bazlı).

### 5. WebSocket (Gerçek Zamanlı İletişim)

*   **WS** `/ws/bus/{bus_id}/location`: Belirtilen servis aracının konumu için WebSocket bağlantısı sağlar.
    *   **Şoför:** Konum verisi gönderir.
    *   **Veli:** Konum verisini anlık olarak alır.
    *   **Altyapı:** Redis Pub/Sub mekanizması ile veriler dağıtılır.

## Veri Modelleri

Sistemde kullanılan temel veri varlıkları:

*   **User:** Sistem kullanıcıları (Admin, Şoför, Veli).
*   **Student:** Öğrenciler.
*   **School:** Okullar.
*   **Bus:** Servis araçları.
*   **BusLocation:** Servis araçlarının konum geçmişi.
*   **AttendanceLog:** Öğrenci yoklama kayıtları (Bindi/İndi).
*   **StudentBusAssignment:** Öğrenci ve servis eşleştirmesi.
*   **ParentStudentRelation:** Veli ve öğrenci ilişkisi.

## Teknik Altyapı

*   **Dil:** Python 3.x
*   **Framework:** FastAPI
*   **Veritabanı:** PostgreSQL (SQLAlchemy ORM, Alembic Migrations)
*   **Önbellek & Mesajlaşma:** Redis
*   **Güvenlik:** OAuth2, JWT
*   **Dokümantasyon:** Swagger UI (`/docs`), ReDoc (`/redoc`)
