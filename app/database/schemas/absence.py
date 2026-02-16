from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AbsenceStatusResponse(BaseModel):
    is_absent_today: bool
    updated_at: Optional[datetime] = None
