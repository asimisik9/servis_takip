"""
Firebase Cloud Messaging (FCM) Notification Service

Velilere push notification göndermek için kullanılır.
Bildirim türleri:
- eve_varis_eta: Eve gelmesine X dakika
- evden_alim_eta: Evden alınmasına X dakika
- okula_varis: Öğrenciler okula vardı
- eve_birakildi: Öğrenci evinde indirildi
- genel: Genel bildirim
"""

import asyncio
import logging
import uuid
from typing import Optional, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException

from ..database.models.notification import (
    Notification as NotificationModel,
    NotificationStatus,
    NotificationType,
)
from ..database.models.user import User as UserModel
from ..database.models.student import Student as StudentModel
from ..database.models.bus import Bus as BusModel
from ..database.models.parent_student_relation import ParentStudentRelation
from ..database.models.student_bus_assignment import StudentBusAssignment
from ..core.config import settings
from ..database.schemas.user import User as UserSchema

logger = logging.getLogger(__name__)

# Firebase SDK - lazy initialization
_firebase_app = None


def _init_firebase():
    """Firebase Admin SDK'yı lazy olarak başlat."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred_path = settings.FIREBASE_CREDENTIALS_PATH
        if not cred_path:
            logger.warning(
                "FIREBASE_CREDENTIALS_PATH ayarlanmamış. "
                "Push notification gönderilemez, sadece DB'ye kaydedilir."
            )
            return None

        cred = credentials.Certificate(cred_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK başarıyla başlatıldı.")
        return _firebase_app
    except Exception as e:
        logger.error(f"Firebase başlatma hatası: {e}")
        return None


def _get_notification_content(
    notification_type: NotificationType,
    student_name: str = "",
    eta_minutes: int = 0,
) -> dict:
    """Bildirim türüne göre başlık ve mesaj oluştur."""
    templates = {
        NotificationType.eve_varis_eta: {
            "title": "🚌 Servis Yaklaşıyor",
            "body": f"{student_name} eve yaklaşık {eta_minutes} dakika içinde varacak.",
        },
        NotificationType.evden_alim_eta: {
            "title": "🚌 Servis Geliyor",
            "body": f"{student_name} için servis yaklaşık {eta_minutes} dakika içinde kapınızda olacak.",
        },
        NotificationType.okula_varis: {
            "title": "✅ Okula Varış",
            "body": f"{student_name} okula güvenle ulaştı.",
        },
        NotificationType.eve_birakildi: {
            "title": "🏠 Eve Bırakıldı",
            "body": f"{student_name} evinde güvenle indirildi.",
        },
        NotificationType.genel: {
            "title": "📢 Servis Now",
            "body": student_name if student_name else "Yeni bir bildiriminiz var.",
        },
    }
    return templates.get(
        notification_type,
        {"title": "Servis Now", "body": "Yeni bildirim."},
    )


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _is_student_in_user_scope(self, sender_user: UserSchema, student_id: str) -> bool:
        role = sender_user.role.value

        if role == "super_admin":
            return True

        if role == "admin":
            if not sender_user.organization_id:
                return False

            admin_scope_query = (
                select(StudentModel.id)
                .where(
                    StudentModel.id == student_id,
                    StudentModel.organization_id == sender_user.organization_id,
                )
            )
            return (await self.db.execute(admin_scope_query)).scalar_one_or_none() is not None

        if role == "sofor":
            driver_scope_query = (
                select(StudentBusAssignment.id)
                .join(BusModel, BusModel.id == StudentBusAssignment.bus_id)
                .join(StudentModel, StudentModel.id == StudentBusAssignment.student_id)
                .where(
                    StudentBusAssignment.student_id == student_id,
                    BusModel.current_driver_id == sender_user.id,
                    StudentModel.organization_id == sender_user.organization_id,
                )
            )
            return (await self.db.execute(driver_scope_query)).scalar_one_or_none() is not None

        return False

    async def _is_recipient_in_user_scope(
        self,
        sender_user: UserSchema,
        recipient_id: str,
        student_id: Optional[str] = None,
    ) -> bool:
        role = sender_user.role.value

        if role == "super_admin":
            return True

        if role != "admin":
            return False

        recipient = await self.db.get(UserModel, recipient_id)
        if not recipient:
            return False

        if not sender_user.organization_id:
            return False

        return recipient.organization_id == sender_user.organization_id

    async def prevalidate_bulk_notification_targets(
        self,
        sender_user: UserSchema,
        recipient_ids: List[str],
        student_id: Optional[str] = None,
    ) -> List[str]:
        """Validate all recipients before sending to avoid partial success on scope errors."""
        unique_recipient_ids = list(dict.fromkeys(recipient_ids))

        if student_id and not await self._is_student_in_user_scope(sender_user, student_id):
            raise HTTPException(status_code=403, detail="Student is out of your tenant scope")

        missing_recipients: List[str] = []
        out_of_scope_recipients: List[str] = []

        for recipient_id in unique_recipient_ids:
            recipient = await self.db.get(UserModel, recipient_id)
            if not recipient:
                missing_recipients.append(recipient_id)
                continue
            if not await self._is_recipient_in_user_scope(sender_user, recipient_id, student_id=student_id):
                out_of_scope_recipients.append(recipient_id)

        if missing_recipients:
            raise HTTPException(
                status_code=404,
                detail=f"Some recipients were not found: {', '.join(missing_recipients)}",
            )
        if out_of_scope_recipients:
            raise HTTPException(
                status_code=403,
                detail=f"Some recipients are out of your tenant scope: {', '.join(out_of_scope_recipients)}",
            )

        return unique_recipient_ids

    # ──────────────────────────── FCM Token ────────────────────────────

    async def register_fcm_token(self, user_id: str, fcm_token: str) -> bool:
        """Kullanıcının FCM token'ını kaydet/güncelle."""
        stmt = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(fcm_token=fcm_token)
        )
        await self.db.execute(stmt)
        await self.db.commit()
        logger.info(f"FCM token kaydedildi: user={user_id}")
        return True

    async def remove_fcm_token(self, user_id: str) -> bool:
        """Kullanıcının FCM token'ını sil (logout durumunda)."""
        stmt = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(fcm_token=None)
        )
        await self.db.execute(stmt)
        await self.db.commit()
        logger.info(f"FCM token silindi: user={user_id}")
        return True

    # ──────────────────── Bildirim Gönderme (Tek) ──────────────────────

    async def send_notification(
        self,
        recipient_id: str,
        notification_type: NotificationType,
        title: Optional[str] = None,
        message: Optional[str] = None,
        student_id: Optional[str] = None,
        student_name: str = "",
        eta_minutes: int = 0,
        sender_user: Optional[UserSchema] = None,
    ) -> Optional[NotificationModel]:
        """Tek bir veliye push notification gönder ve DB'ye kaydet."""

        recipient = await self.db.get(UserModel, recipient_id)
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient not found")

        if sender_user:
            if student_id and not await self._is_student_in_user_scope(sender_user, student_id):
                raise HTTPException(status_code=403, detail="Student is out of your tenant scope")

            if not await self._is_recipient_in_user_scope(sender_user, recipient_id, student_id=student_id):
                raise HTTPException(status_code=403, detail="Recipient is out of your tenant scope")

        # Eğer title/message verilmediyse template'ten oluştur
        if not title or not message:
            content = _get_notification_content(
                notification_type, student_name, eta_minutes
            )
            title = title or content["title"]
            message = message or content["body"]

        # DB'ye kaydet
        notification = NotificationModel(
            id=str(uuid.uuid4()),
            recipient_id=recipient_id,
            student_id=student_id,
            title=title,
            message=message,
            notification_type=notification_type,
            status=NotificationStatus.beklemede,
            is_read=False,
        )
        self.db.add(notification)

        # FCM push gönder
        push_success = await self._send_fcm_push(recipient_id, title, message, {
            "notification_type": notification_type.value,
            "student_id": student_id or "",
            "notification_id": notification.id,
        })

        notification.status = (
            NotificationStatus.gonderildi if push_success else NotificationStatus.hatali
        )

        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    # ─────────────── Bildirim Gönderme (Toplu - Öğrenci Bazlı) ───────────────

    async def notify_parents_of_student(
        self,
        student_id: str,
        notification_type: NotificationType,
        sender_user: UserSchema,
        eta_minutes: int = 0,
    ) -> List[NotificationModel]:
        """Bir öğrencinin tüm velilerine bildirim gönder."""
        if not await self._is_student_in_user_scope(sender_user, student_id):
            raise HTTPException(status_code=403, detail="Student is out of your tenant scope")

        # Öğrenci bilgisini al
        student = await self.db.get(StudentModel, student_id)
        if not student:
            logger.warning(f"Öğrenci bulunamadı: {student_id}")
            return []

        # Velileri bul
        query = select(ParentStudentRelation).where(
            ParentStudentRelation.student_id == student_id
        )
        result = await self.db.execute(query)
        relations = result.scalars().all()

        notifications = []
        for relation in relations:
            notif = await self.send_notification(
                recipient_id=relation.parent_id,
                notification_type=notification_type,
                student_id=student_id,
                student_name=student.full_name,
                eta_minutes=eta_minutes,
                sender_user=sender_user,
            )
            if notif:
                notifications.append(notif)

        return notifications

    # ──────────────── Bildirim Listeleme ────────────────

    async def get_user_notifications(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        unread_only: bool = False,
    ) -> List[NotificationModel]:
        """Kullanıcının bildirimlerini listele."""
        query = (
            select(NotificationModel)
            .where(NotificationModel.recipient_id == user_id)
            .order_by(NotificationModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if unread_only:
            query = query.where(NotificationModel.is_read == False)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_unread_count(self, user_id: str) -> int:
        """Okunmamış bildirim sayısını getir."""
        from sqlalchemy import func

        query = select(func.count(NotificationModel.id)).where(
            NotificationModel.recipient_id == user_id,
            NotificationModel.is_read == False,
        )
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """Bildirimi okundu olarak işaretle."""
        stmt = (
            update(NotificationModel)
            .where(
                NotificationModel.id == notification_id,
                NotificationModel.recipient_id == user_id,
            )
            .values(is_read=True)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def mark_all_as_read(self, user_id: str) -> int:
        """Tüm bildirimleri okundu olarak işaretle."""
        stmt = (
            update(NotificationModel)
            .where(
                NotificationModel.recipient_id == user_id,
                NotificationModel.is_read == False,
            )
            .values(is_read=True)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    # ──────────────── FCM Push (Internal) ────────────────

    async def _send_fcm_push(
        self,
        user_id: str,
        title: str,
        body: str,
        data: dict = None,
    ) -> bool:
        """FCM üzerinden push notification gönder."""
        # Kullanıcının FCM token'ını al
        user = await self.db.get(UserModel, user_id)
        if not user or not user.fcm_token:
            logger.info(f"FCM token bulunamadı: user={user_id}. Push atlalandı.")
            return False

        firebase_app = _init_firebase()
        if not firebase_app:
            logger.warning("Firebase başlatılamamış. Push gönderilemedi.")
            return False

        try:
            from firebase_admin import messaging

            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data={k: str(v) for k, v in (data or {}).items()},
                token=user.fcm_token,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        sound="default",
                        channel_id="servis_now_notifications",
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound="default",
                            badge=1,
                        ),
                    ),
                ),
            )

            # C6: Wrap sync Firebase call to avoid blocking the event loop
            response = await asyncio.to_thread(messaging.send, message)
            logger.info(f"FCM push gönderildi: user={user_id}, response={response}")
            return True

        except Exception as e:
            error_str = str(e)
            # Token geçersizse sil
            if "UNREGISTERED" in error_str or "INVALID_ARGUMENT" in error_str:
                logger.warning(f"Geçersiz FCM token siliniyor: user={user_id}")
                await self.remove_fcm_token(user_id)
            else:
                logger.error(f"FCM push hatası: user={user_id}, error={e}")
            return False
