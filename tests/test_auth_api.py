import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from datetime import datetime, timedelta, timezone
import hashlib

from magentic_ui.backend.web.app import create_app # Main app factory
from magentic_ui.backend.web.deps import get_session # To override
from magentic_ui.backend.datamodel.db import User, WhitelistedDomain, LoginCode
from magentic_ui.backend.datamodel.types import RequestCodeRequest, VerifyCodeRequest, DomainCreateRequest

# In-memory SQLite database for testing
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Dependency override for session
def override_get_session():
    with Session(engine) as session:
        yield session

@pytest.fixture(scope="function", name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(scope="function", name="client")
def client_fixture(session: Session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        yield client

@pytest.fixture(scope="function", name="test_user_email")
def test_user_email_fixture():
    return "test@example.com"

@pytest.fixture(scope="function", name="admin_user_email")
def admin_user_email_fixture():
    return "admin@example.com"

@pytest.fixture(scope="function")
def whitelisted_domain_fixture(session: Session):
    domain = WhitelistedDomain(domain="example.com")
    session.add(domain)
    session.commit()
    session.refresh(domain)
    return domain

@pytest.fixture(scope="function")
def wildcard_whitelisted_domain_fixture(session: Session):
    domain = WhitelistedDomain(domain="*") # Wildcard for any domain
    session.add(domain)
    session.commit()
    session.refresh(domain)
    return domain
    
@pytest.fixture(scope="function")
def test_user_fixture(session: Session, test_user_email: str):
    user = User(email=test_user_email)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

@pytest.fixture(scope="function")
def admin_user_fixture(session: Session, admin_user_email: str):
    user = User(email=admin_user_email)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

# Helper to generate admin token
def get_admin_auth_headers(admin_email: str = "admin@example.com"):
    token = f"fake-token-for-{admin_email}-adminhex"
    return {"Authorization": f"Bearer {token}"}

# Helper to generate user token
def get_user_auth_headers(user_email: str = "test@example.com"):
    token = f"fake-token-for-{user_email}-userhex"
    return {"Authorization": f"Bearer {token}"}

# Test for /auth/request-code
def test_request_code_success(client: TestClient, session: Session, test_user_email: str, whitelisted_domain_fixture):
    response = client.post("/api/auth/request-code", json={"email": test_user_email})
    assert response.status_code == 200
    assert response.json()["message"] == "Login code sent"

    # Verify LoginCode created
    login_code_entry = session.exec(
        LoginCode.select().join(User).where(User.email == test_user_email)
    ).first()
    assert login_code_entry is not None
    assert login_code_entry.used is False

def test_request_code_new_user_creation(client: TestClient, session: Session, whitelisted_domain_fixture):
    new_email = "newuser@example.com"
    # Ensure user does not exist
    user_before = session.exec(User.select().where(User.email == new_email)).first()
    assert user_before is None
    
    response = client.post("/api/auth/request-code", json={"email": new_email})
    assert response.status_code == 200
    
    user_after = session.exec(User.select().where(User.email == new_email)).first()
    assert user_after is not None
    assert user_after.email == new_email

def test_request_code_non_whitelisted_domain(client: TestClient, session: Session):
    response = client.post("/api/auth/request-code", json={"email": "test@otherdomain.com"})
    assert response.status_code == 403
    assert "not whitelisted" in response.json()["detail"]

def test_request_code_wildcard_domain(client: TestClient, session: Session, wildcard_whitelisted_domain_fixture):
    email_on_other_domain = "test@anotherdomain.com"
    response = client.post("/api/auth/request-code", json={"email": email_on_other_domain})
    assert response.status_code == 200
    assert response.json()["message"] == "Login code sent"

    login_code_entry = session.exec(
        LoginCode.select().join(User).where(User.email == email_on_other_domain)
    ).first()
    assert login_code_entry is not None


# Tests for /auth/verify-code
@pytest.fixture(scope="function")
def login_code_fixture(session: Session, test_user_fixture: User):
    code = "123456"
    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    login_code = LoginCode(
        user_id=test_user_fixture.id,
        code_hash=code_hash,
        expires_at=expires_at,
        used=False,
    )
    session.add(login_code)
    session.commit()
    session.refresh(login_code)
    return login_code, code # Return plain code for use in tests

def test_verify_code_success(client: TestClient, session: Session, test_user_email: str, test_user_fixture: User, login_code_fixture):
    _, plain_code = login_code_fixture
    response = client.post("/api/auth/verify-code", json={"email": test_user_email, "code": plain_code})
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["token"].startswith("fake-token-for-")
    
    db_code = session.get(LoginCode, login_code_fixture[0].id)
    assert db_code.used is True

def test_verify_code_invalid_code(client: TestClient, test_user_email: str, test_user_fixture: User, login_code_fixture):
    response = client.post("/api/auth/verify-code", json={"email": test_user_email, "code": "WRONGCODE"})
    assert response.status_code == 400
    assert "Invalid or expired code" in response.json()["detail"]

def test_verify_code_expired_code(client: TestClient, session: Session, test_user_email: str, test_user_fixture: User, login_code_fixture):
    db_code, plain_code = login_code_fixture
    db_code.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.add(db_code)
    session.commit()
    
    response = client.post("/api/auth/verify-code", json={"email": test_user_email, "code": plain_code})
    assert response.status_code == 400
    assert "Invalid or expired code" in response.json()["detail"]

def test_verify_code_used_code(client: TestClient, session: Session, test_user_email: str, test_user_fixture: User, login_code_fixture):
    db_code, plain_code = login_code_fixture
    db_code.used = True
    session.add(db_code)
    session.commit()

    response = client.post("/api/auth/verify-code", json={"email": test_user_email, "code": plain_code})
    assert response.status_code == 400
    assert "Invalid or expired code" in response.json()["detail"]

def test_verify_code_non_existent_user(client: TestClient, login_code_fixture):
    _, plain_code = login_code_fixture
    response = client.post("/api/auth/verify-code", json={"email": "nosuchuser@example.com", "code": plain_code})
    assert response.status_code == 404 # User not found
    assert "User not found" in response.json()["detail"]

# Tests for Admin Domain Management Endpoints
NEW_DOMAIN = "newdomain.com"

def test_admin_add_domain_success(client: TestClient, session: Session, admin_user_fixture):
    admin_email = admin_user_fixture.email
    response = client.post(
        "/api/auth/admin/domains",
        json={"domain": NEW_DOMAIN},
        headers=get_admin_auth_headers(admin_email)
    )
    assert response.status_code == 201
    data = response.json()
    assert data["domain"] == NEW_DOMAIN
    
    db_domain = session.exec(WhitelistedDomain.select().where(WhitelistedDomain.domain == NEW_DOMAIN)).first()
    assert db_domain is not None

def test_admin_add_domain_duplicate(client: TestClient, session: Session, admin_user_fixture, whitelisted_domain_fixture):
    admin_email = admin_user_fixture.email
    response = client.post(
        "/api/auth/admin/domains",
        json={"domain": "example.com"}, # Domain from fixture
        headers=get_admin_auth_headers(admin_email)
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]

def test_admin_add_domain_no_auth(client: TestClient):
    response = client.post("/api/auth/admin/domains", json={"domain": "another.com"})
    assert response.status_code == 401 # Expecting unauthorized due to missing Depends(get_current_user) handling or direct HTTPUnauthorized from scheme if token is empty

def test_admin_list_domains_success(client: TestClient, session: Session, admin_user_fixture, whitelisted_domain_fixture):
    admin_email = admin_user_fixture.email
    response = client.get("/api/auth/admin/domains", headers=get_admin_auth_headers(admin_email))
    assert response.status_code == 200
    data = response.json()
    assert "domains" in data
    assert len(data["domains"]) >= 1
    assert any(d["domain"] == "example.com" for d in data["domains"])

def test_admin_list_domains_no_auth(client: TestClient):
    response = client.get("/api/auth/admin/domains")
    assert response.status_code == 401

def test_admin_delete_domain_success(client: TestClient, session: Session, admin_user_fixture, whitelisted_domain_fixture):
    admin_email = admin_user_fixture.email
    domain_id_to_delete = whitelisted_domain_fixture.id
    
    response = client.delete(
        f"/api/auth/admin/domains/{domain_id_to_delete}",
        headers=get_admin_auth_headers(admin_email)
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Domain deleted successfully"
    
    deleted_domain = session.get(WhitelistedDomain, domain_id_to_delete)
    assert deleted_domain is None

def test_admin_delete_domain_not_found(client: TestClient, admin_user_fixture):
    admin_email = admin_user_fixture.email
    non_existent_id = 99999
    response = client.delete(
        f"/api/auth/admin/domains/{non_existent_id}",
        headers=get_admin_auth_headers(admin_email)
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

def test_admin_delete_domain_no_auth(client: TestClient, whitelisted_domain_fixture):
    domain_id_to_delete = whitelisted_domain_fixture.id
    response = client.delete(f"/api/auth/admin/domains/{domain_id_to_delete}")
    assert response.status_code == 401

# Conceptual test for User Data Isolation (Sessions)
# This would typically be in a test_sessions_api.py but included here for concept.
# It assumes Session model has user_id linked to User.id (integer)
# and that sessions endpoints are protected by get_current_user

# @pytest.mark.skip(reason="Conceptual test, depends on Session model and routes structure")
def test_session_data_isolation(client: TestClient, session: Session):
    # 1. Create users
    user1_email = "user1@example.com"
    user2_email = "user2@example.com"
    user1 = User(email=user1_email)
    user2 = User(email=user2_email)
    session.add_all([user1, user2])
    session.commit()
    session.refresh(user1)
    session.refresh(user2)

    # Create a whitelisted domain if not already present by other fixtures
    if not session.exec(WhitelistedDomain.select().where(WhitelistedDomain.domain == "example.com")).first():
        domain = WhitelistedDomain(domain="example.com")
        session.add(domain)
        session.commit()

    # 2. Create sessions for each user (simplified, assumes Session model can be created directly)
    # In a real scenario, you might need to call the POST /api/sessions endpoint
    # which itself should be protected and associate the session with the current_user
    
    # User 1 creates a session via API (assuming POST /api/sessions is protected)
    client.post("/api/sessions/", json={"name": "User1 Session1"}, headers=get_user_auth_headers(user1_email))
    
    # User 2 creates a session via API
    client.post("/api/sessions/", json={"name": "User2 Session1"}, headers=get_user_auth_headers(user2_email))
    client.post("/api/sessions/", json={"name": "User2 Session2"}, headers=get_user_auth_headers(user2_email))

    # 3. List sessions as user1
    response_user1 = client.get("/api/sessions/", headers=get_user_auth_headers(user1_email))
    assert response_user1.status_code == 200
    sessions_user1 = response_user1.json().get("data", [])
    
    # Assert only user1's sessions are returned
    assert len(sessions_user1) == 1
    # Check if the session name matches or if user_id (int) matches user1.id
    # This depends on the actual structure of the Session model and how user_id is stored.
    # For this conceptual test, we assume the endpoint filters correctly.
    # Example check if user_id is directly in the session dict:
    for sess_dict in sessions_user1:
         assert sess_dict.get("user_id") == user1.id # Assuming user_id is int in Session model
         assert sess_dict.get("name") == "User1 Session1"


    # 4. List sessions as user2
    response_user2 = client.get("/api/sessions/", headers=get_user_auth_headers(user2_email))
    assert response_user2.status_code == 200
    sessions_user2 = response_user2.json().get("data", [])
    
    assert len(sessions_user2) == 2
    for sess_dict in sessions_user2:
         assert sess_dict.get("user_id") == user2.id # Assuming user_id is int
         assert "User2 Session" in sess_dict.get("name")

    # 5. Ensure user1 cannot get user2's specific session (conceptual)
    # Assuming /api/sessions/{session_id} is also protected and checks ownership
    # This requires knowing an ID of a session belonging to user2.
    # For now, this is a conceptual point.
    # For example, if sessions_user2[0] has id `s2_id`:
    # resp_get_s2_as_s1 = client.get(f"/api/sessions/{s2_id}", headers=get_user_auth_headers(user1_email))
    # assert resp_get_s2_as_s1.status_code == 404 # or 403

```
