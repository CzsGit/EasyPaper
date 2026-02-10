from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlmodel import Session

from ..core.config import get_config
from ..core.db import get_session
from ..core.security import ALGORITHM
from ..models.user import TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(session: Session = Depends(get_session), token: str = Depends(reusable_oauth2)) -> User:
    config = get_config()
    try:
        payload = jwt.decode(token, config.security.secret_key, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError) as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        ) from err
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user
