import os
import uuid
from time import sleep

import httpx
import pytest


pytestmark = [pytest.mark.e2e, pytest.mark.slow]

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")
TENANT_ADMIN_EMAIL = "okul.admin@salihlikoleji.com"
TENANT_ADMIN_PASSWORD = "Test1234!"
TENANT_ORG_ID = "sch0-0000-0000-0000-000000000001"
OTHER_ORG_ID = "trn1-0000-0000-0000-000000000001"


@pytest.fixture(scope="session")
def api_client():
    client = httpx.Client(base_url=BASE_URL, timeout=15.0, follow_redirects=True)
    yield client
    client.close()


@pytest.fixture(scope="session", autouse=True)
def wait_for_backend(api_client):
    last_error = None
    for _ in range(30):
        try:
            response = api_client.get("/health")
            if response.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        sleep(1)

    pytest.fail(f"Backend is not reachable at {BASE_URL}. Last error: {last_error}")


@pytest.fixture
def tenant_admin_token(api_client):
    response = api_client.post(
        "/api/auth/login",
        data={
            "grant_type": "password",
            "username": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_health_and_readiness_endpoints_are_healthy(api_client):
    health = api_client.get("/health")
    readiness = api_client.get("/readiness")

    assert health.status_code == 200
    assert health.json() == {"status": "healthy"}
    assert readiness.status_code == 200
    assert readiness.json() == {"status": "ready"}


def test_verified_tenant_admin_can_login_and_fetch_profile(api_client):
    response = api_client.post(
        "/api/auth/login",
        data={
            "grant_type": "password",
            "username": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["token_type"] == "bearer"
    assert payload["user"]["email"] == TENANT_ADMIN_EMAIL

    me_response = api_client.get("/api/auth/me", headers=auth_headers(payload["access_token"]))
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["organization_id"] == TENANT_ORG_ID


def test_tenant_admin_list_endpoints_ignore_cross_tenant_filters(api_client, tenant_admin_token):
    users_response = api_client.get(
        "/api/admin/users",
        headers=auth_headers(tenant_admin_token),
        params={"organization_id": OTHER_ORG_ID, "limit": 100},
    )
    students_response = api_client.get(
        "/api/admin/students",
        headers=auth_headers(tenant_admin_token),
        params={"organization_id": OTHER_ORG_ID, "limit": 100},
    )

    assert users_response.status_code == 200, users_response.text
    assert students_response.status_code == 200, students_response.text

    users_payload = users_response.json()
    students_payload = students_response.json()

    assert users_payload["items"]
    assert students_payload["items"]
    assert {item["organization_id"] for item in users_payload["items"]} == {TENANT_ORG_ID}
    assert {item["organization_id"] for item in students_payload["items"]} == {TENANT_ORG_ID}


def test_tenant_admin_can_create_update_and_soft_delete_user(api_client, tenant_admin_token):
    suffix = uuid.uuid4().hex[:8]
    phone_suffix = str(uuid.uuid4().int)[-8:]
    create_response = api_client.post(
        "/api/admin/users",
        headers=auth_headers(tenant_admin_token),
        json={
            "full_name": f"E2E User {suffix}",
            "email": f"e2e.user.{suffix}@example.com",
            "phone_number": f"+90555{phone_suffix}",
            "password": "StrongPass1",
            "role": "veli",
            "organization_id": OTHER_ORG_ID,
        },
    )

    assert create_response.status_code == 201, create_response.text
    created_user = create_response.json()
    assert created_user["organization_id"] == TENANT_ORG_ID
    created_user_id = created_user["id"]

    list_response = api_client.get(
        "/api/admin/users",
        headers=auth_headers(tenant_admin_token),
        params={"limit": 100},
    )
    assert list_response.status_code == 200, list_response.text
    listed_ids = {item["id"] for item in list_response.json()["items"]}
    assert created_user_id in listed_ids

    update_response = api_client.put(
        f"/api/admin/users/{created_user_id}",
        headers=auth_headers(tenant_admin_token),
        json={
            "full_name": f"E2E User Updated {suffix}",
            "organization_id": OTHER_ORG_ID,
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated_user = update_response.json()
    assert updated_user["full_name"] == f"E2E User Updated {suffix}"
    assert updated_user["organization_id"] == TENANT_ORG_ID

    delete_response = api_client.delete(
        f"/api/admin/users/{created_user_id}",
        headers=auth_headers(tenant_admin_token),
    )
    assert delete_response.status_code == 200, delete_response.text

    get_response = api_client.get(
        f"/api/admin/users/{created_user_id}",
        headers=auth_headers(tenant_admin_token),
    )
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["is_active"] is False
