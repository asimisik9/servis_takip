from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from sqlalchemy.ext.asyncio import AsyncSession
from ..database.database import AsyncSessionLocal
from ..database.models.audit_log import AuditLog
from ..routers.auth import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError
from uuid import uuid4
from datetime import datetime
import json

class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Process the request
        response = await call_next(request)
        
        # We only want to log requests to /api/admin
        # You can adjust this filter as needed
        if not request.url.path.startswith("/api/admin"):
            return response

        # Extract user info from token
        user_id = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                user_id = payload.get("id")
            except JWTError:
                pass
        
        # Log to database
        # We need to create a new session because we are outside of the dependency injection system
        async with AsyncSessionLocal() as session:
            try:
                audit_log = AuditLog(
                    id=str(uuid4()),
                    user_id=user_id,
                    action=request.method,
                    endpoint=request.url.path,
                    status_code=response.status_code,
                    timestamp=datetime.utcnow(),
                    details=str(request.query_params) if request.query_params else None
                )
                session.add(audit_log)
                await session.commit()
            except Exception as e:
                print(f"Error logging audit: {e}")
                
        return response
