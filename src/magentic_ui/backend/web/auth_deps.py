from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from loguru import logger

from magentic_ui.backend.datamodel.db import User
from magentic_ui.backend.web.deps import get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token") # Dummy tokenUrl

async def get_current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token.startswith("fake-token-for-"):
        logger.warning(f"Token does not start with 'fake-token-for-'. Token: {token}")
        raise credentials_exception

    try:
        # Extract email from token (e.g., "fake-token-for-user@example.com-randomhex")
        # The user's email is between "fake-token-for-" and the last "-"
        parts = token.split("-")
        if len(parts) < 4: # "fake", "token", "for", "emailpart...", "randomhex"
            logger.warning(f"Token malformed, not enough parts. Token: {token}")
            raise credentials_exception
        
        # Reconstruct email which might contain '-'
        # Email is parts[3] up to parts[-2] joined by '-'
        email_parts = parts[3:-1]
        if not email_parts:
            logger.warning(f"Token malformed, no email parts found. Token: {token}")
            raise credentials_exception
        user_email = "-".join(email_parts)

        if not user_email: # Should be caught by previous checks, but good to be sure
            logger.warning(f"Extracted email is empty. Token: {token}")
            raise credentials_exception
        
        logger.debug(f"Attempting to find user by email: {user_email}")

    except Exception as e:
        logger.error(f"Error processing token: {e}. Token: {token}")
        raise credentials_exception from e

    user = session.exec(select(User).where(User.email == user_email)).first()
    if user is None:
        logger.warning(f"User not found for email: {user_email}, extracted from token.")
        raise credentials_exception
    
    logger.info(f"User {user.email} authenticated successfully via token.")
    return user
