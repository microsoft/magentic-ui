from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from datetime import datetime, timedelta, timezone
import secrets
import hashlib
from loguru import logger

from magentic_ui.backend.datamodel.db import User, LoginCode, WhitelistedDomain
from magentic_ui.backend.datamodel.types import (
    RequestCodeRequest,
    VerifyCodeRequest,
    AuthSuccessResponse,
    ResponseMessage,
    DomainCreateRequest,
    WhitelistedDomainResponse,
    DomainListResponse,
)
from magentic_ui.backend.web.deps import get_session
from magentic_ui.backend.web.auth_deps import get_current_user

router = APIRouter()

# Placeholder for JWT secret and algorithm - should be in config
JWT_SECRET = "your-secret-key" # Replace with a strong, configured secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


@router.post("/request-code", response_model=ResponseMessage)
async def request_code(
    request: RequestCodeRequest, session: Session = Depends(get_session)
):
    email_domain = request.email.split("@")[1]
    
    whitelisted_domain = session.exec(
        select(WhitelistedDomain).where(WhitelistedDomain.domain == email_domain)
    ).first()
    
    if not whitelisted_domain:
        # Check for wildcard domain
        wildcard_domain_entry = session.exec(
            select(WhitelistedDomain).where(WhitelistedDomain.domain == "*")
        ).first()
        if not wildcard_domain_entry:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Email domain {email_domain} is not whitelisted.",
            )

    user = session.exec(select(User).where(User.email == request.email)).first()
    if not user:
        user = User(email=request.email)
        session.add(user)
        session.commit()
        session.refresh(user)
        logger.info(f"New user created: {user.email}")

    code = secrets.token_hex(3).upper()  # 6-character alphanumeric code
    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    login_code = LoginCode(
        user_id=user.id,
        code_hash=code_hash,
        expires_at=expires_at,
        used=False,
    )
    session.add(login_code)
    session.commit()

    logger.info(f"Login code for {request.email}: {code}")  # Placeholder for email sending

    return ResponseMessage(message="Login code sent")


@router.post("/verify-code", response_model=AuthSuccessResponse)
async def verify_code(
    request: VerifyCodeRequest, session: Session = Depends(get_session)
):
    user = session.exec(select(User).where(User.email == request.email)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    code_hash = hashlib.sha256(request.code.encode("utf-8")).hexdigest()
    
    now = datetime.now(timezone.utc)

    login_code_entry = session.exec(
        select(LoginCode)
        .where(LoginCode.user_id == user.id)
        .where(LoginCode.code_hash == code_hash)
        .where(LoginCode.used == False)
        .where(LoginCode.expires_at > now)
    ).first()

    if not login_code_entry:
        logger.warning(
            f"Invalid or expired code attempt for user {request.email}. Provided code: {request.code}"
        )
        # Check if any code exists to differentiate between expired and never_existed/wrong_code
        existing_code_debug = session.exec(
            select(LoginCode)
            .where(LoginCode.user_id == user.id)
            .where(LoginCode.code_hash == code_hash)
        ).first()
        if existing_code_debug:
            logger.warning(f"Code found but it's either used (Used: {existing_code_debug.used}) or expired (Expires: {existing_code_debug.expires_at}, Now: {now})")
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code.",
        )

    login_code_entry.used = True
    login_code_entry.updated_at = datetime.now(timezone.utc) # Assuming LoginCode has updated_at
    session.add(login_code_entry)
    session.commit()

    # Placeholder for actual JWT generation
    # from jose import jwt # Would be needed for real JWTs
    # access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # expire = datetime.now(timezone.utc) + access_token_expires
    # to_encode = {"sub": user.email, "exp": expire}
    # access_token = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    
    access_token = f"fake-token-for-{user.email}-{secrets.token_hex(16)}" # Simple fake token

    logger.info(f"User {user.email} successfully verified.")
    return AuthSuccessResponse(token=access_token)


# Admin routes for whitelisted domains
admin_router = APIRouter(prefix="/admin")


@admin_router.post(
    "/domains",
    response_model=WhitelistedDomainResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_whitelisted_domain(
    request: DomainCreateRequest, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # TODO: Implement actual admin role check for current_user
    logger.info(f"Admin action: User {current_user.email} adding domain {request.domain}")
    existing_domain = session.exec(
        select(WhitelistedDomain).where(WhitelistedDomain.domain == request.domain)
    ).first()
    if existing_domain:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Domain already exists in whitelist.",
        )

    db_domain = WhitelistedDomain(domain=request.domain)
    session.add(db_domain)
    session.commit()
    session.refresh(db_domain)
    return db_domain


@admin_router.get("/domains", response_model=DomainListResponse)
async def list_whitelisted_domains(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # TODO: Implement actual admin role check for current_user
    logger.info(f"Admin action: User {current_user.email} listing domains")
    domains = session.exec(select(WhitelistedDomain)).all()
    return DomainListResponse(domains=[WhitelistedDomainResponse.from_orm(d) for d in domains])


@admin_router.delete("/domains/{domain_id}", response_model=ResponseMessage)
async def delete_whitelisted_domain(
    domain_id: int, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # TODO: Implement actual admin role check for current_user
    logger.info(f"Admin action: User {current_user.email} deleting domain ID {domain_id}")
    domain_to_delete = session.get(WhitelistedDomain, domain_id)
    if not domain_to_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found in whitelist.",
        )

    session.delete(domain_to_delete)
    session.commit()
    return ResponseMessage(message="Domain deleted successfully")

router.include_router(admin_router)
