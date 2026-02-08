"""
Bus Locations Cleanup Task

Eski konum verilerini temizler.
bus_locations tablosu 50 otobüs x 12 kayıt/dk = 864K satır/gün üretir.
7 günden eski verileri silerek tablo boyutunu kontrol altında tutar.

Kullanım (cron job):
  python -m app.tasks.cleanup_bus_locations
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, func, select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RETENTION_DAYS = 7


async def cleanup_old_bus_locations(retention_days: int = RETENTION_DAYS) -> int:
    from ..database.database import AsyncSessionLocal
    from ..database.models.bus_location import BusLocation
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    
    async with AsyncSessionLocal() as db:
        count_query = select(func.count()).select_from(BusLocation).where(BusLocation.timestamp < cutoff)
        result = await db.execute(count_query)
        total = result.scalar()
        
        if total == 0:
            logger.info(f"No bus_locations older than {retention_days} days.")
            return 0
        
        logger.info(f"Cleaning up {total} bus_locations older than {retention_days} days...")
        
        batch_size = 10000
        deleted_total = 0
        
        while True:
            subquery = (
                select(BusLocation.id)
                .where(BusLocation.timestamp < cutoff)
                .limit(batch_size)
            )
            stmt = delete(BusLocation).where(BusLocation.id.in_(subquery))
            result = await db.execute(stmt)
            await db.commit()
            
            batch_deleted = result.rowcount
            deleted_total += batch_deleted
            
            if batch_deleted < batch_size:
                break
            
            logger.info(f"  Deleted {deleted_total}/{total} rows...")
        
        logger.info(f"Cleanup complete: deleted {deleted_total} rows.")
        return deleted_total


if __name__ == "__main__":
    asyncio.run(cleanup_old_bus_locations())
