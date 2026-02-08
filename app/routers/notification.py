"""
Notification Router — Bildirim API Endpoints

Endpoints:
- POST /notifications/fcm-token       → FCM token kaydet
- DELETE /notifications/fcm-token      → FCM token sil (logout)
- GET  /notifications/                 → Bildirimleri listele
- GET  /notifications/unread-count     → Okunmamış sayısı
- PUT  /notifications/{id}/read        → Okundu olarak işaretle
- PUT  /notifications/read-all         → Tümünü okundu işaretle
- POST /notifications/send             → Bildirim gönder (admin/sistem)
- POST /notifications/student/{id}/notify → Öğrenci velilerine bildirim
"""

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from typing import List, Annotated
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db, get_current_parent_user, get_current_user, get_current_admin_user
from ..core.limiter import limiter
from ..database.schemas.notification import (
    Notification,
    NotificationResponse,
    FCMTokenRegister,
    SendNotificationRequest,
    NotificationType,
)
from ..database.schemas.user import User
from ..services.notification_service import NotificationService
from ..database.models.notification import NotificationType as NotificationTypeModel

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)


# ──────────────── FCM Token Yönetimi ────────────────

@router.post("/fcm-token", response_model=NotificationResponse)
async def register_fcm_token(
    body: FCMTokenRegister,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Kullanıcının FCM token'ını kaydet/güncelle.
    Her login veya app açılışında çağrılmalı.
    """
    service = NotificationService(db)
    await service.register_fcm_token(current_user.id, body.fcm_token)
    return NotificationResponse(success=True, message="FCM token kaydedildi")


@router.delete("/fcm-token", response_model=NotificationResponse)
async def remove_fcm_token(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Kullanıcının FCM token'ını sil.
    Logout sırasında çağrılmalı.
    """
    service = NotificationService(db)
    await service.remove_fcm_token(current_user.id)
    return NotificationResponse(success=True, message="FCM token silindi")


# ──────────────── Bildirim Listeleme ────────────────

@router.get("/", response_model=List[Notification])
async def get_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    unread_only: bool = Query(default=False),
):
    """
    Kullanıcının bildirimlerini listele.
    Pagination ve unread_only filtresi destekler.
    """
    service = NotificationService(db)
    return await service.get_user_notifications(
        current_user.id, skip=skip, limit=limit, unread_only=unread_only
    )


@router.get("/unread-count")
async def get_unread_count(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """Okunmamış bildirim sayısını döner."""
    service = NotificationService(db)
    count = await service.get_unread_count(current_user.id)
    return {"unread_count": count}


# ──────────────── Bildirim Okundu İşaretleme ────────────────

@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """Bildirimi okundu olarak işaretle."""
    service = NotificationService(db)
    success = await service.mark_as_read(notification_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Bildirim bulunamadı")
    return NotificationResponse(success=True, message="Bildirim okundu olarak işaretlendi")


@router.put("/read-all", response_model=NotificationResponse)
async def mark_all_notifications_read(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """Tüm bildirimleri okundu olarak işaretle."""
    service = NotificationService(db)
    count = await service.mark_all_as_read(current_user.id)
    return NotificationResponse(
        success=True, message=f"{count} bildirim okundu olarak işaretlendi"
    )


# ──────────────── Bildirim Gönderme (Sistem/Admin) ────────────────

@router.post("/send", response_model=NotificationResponse)
@limiter.limit("30/minute")
async def send_notification(
    request: Request,
    body: SendNotificationRequest,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Belirli kullanıcılara bildirim gönder.
    Admin veya sistem tarafından kullanılır.
    """
    service = NotificationService(db)
    sent_count = 0
    for recipient_id in body.recipient_ids:
        notif = await service.send_notification(
            recipient_id=recipient_id,
            notification_type=NotificationTypeModel(body.notification_type.value),
            title=body.title,
            message=body.message,
            student_id=body.student_id,
        )
        if notif:
            sent_count += 1

    return NotificationResponse(
        success=True,
        message=f"{sent_count}/{len(body.recipient_ids)} bildirim gönderildi",
    )


@router.post("/student/{student_id}/notify", response_model=NotificationResponse)
@limiter.limit("60/minute")
async def notify_student_parents(
    request: Request,
    student_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    notification_type: NotificationType = Query(...),
    eta_minutes: int = Query(default=0, ge=0),
):
    """
    Bir öğrencinin tüm velilerine bildirim gönder.
    Sadece şoför veya admin tarafından kullanılabilir.
    Örn: Öğrenci okula vardı, eve bırakıldı, ETA bildirimi.
    """
    # Only drivers and admins can send student notifications
    if current_user.role.value not in ("sofor", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Only drivers and admins can send student notifications"
        )
    
    service = NotificationService(db)
    notifications = await service.notify_parents_of_student(
        student_id=student_id,
        notification_type=NotificationTypeModel(notification_type.value),
        eta_minutes=eta_minutes,
    )
    return NotificationResponse(
        success=True,
        message=f"{len(notifications)} veliye bildirim gönderildi",
    )
