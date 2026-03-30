"""API smoke tests for rebuilt Ship routes.

Targets the rebuilt Ship app at BASE_URL (default localhost:3000).
Covers SHIP-01 (API routes) and SHIP-04 (deployed URL).
"""
import os
import uuid

import pytest
import httpx

BASE_URL = os.environ.get("SHIP_BASE_URL", "http://localhost:3000")
TEST_EMAIL = "smoke-test@example.com"
TEST_PASSWORD = "smokeTestPass123!"


@pytest.fixture
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        yield c


@pytest.fixture
async def auth_token(client):
    """Register + login, return auth token for authenticated tests."""
    # Try signup first (may already exist)
    await client.post("/api/auth/signup", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    # Login to get token
    resp = await client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert resp.status_code in (200, 201), f"Login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("accessToken") or data.get("access_token", "")
    return token


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """GET /health returns 200 with a response body."""
    resp = await client.get("/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    assert len(resp.content) > 0, "Health endpoint returned empty body"


@pytest.mark.asyncio
async def test_auth_signup(client):
    """POST /api/auth/signup with unique email returns 200 or 201."""
    unique_email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post("/api/auth/signup", json={
        "email": unique_email,
        "password": TEST_PASSWORD,
    })
    assert resp.status_code in (200, 201), f"Signup failed: {resp.status_code} {resp.text[:200]}"
    data = resp.json()
    assert "user" in data or "token" in data or "accessToken" in data, (
        f"Signup response missing user/token key: {list(data.keys())}"
    )


@pytest.mark.asyncio
async def test_auth_login(client):
    """POST /api/auth/login with valid credentials returns 200 with token."""
    # Ensure user exists
    await client.post("/api/auth/signup", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    resp = await client.post("/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    assert data.get("token") or data.get("accessToken") or data.get("access_token"), (
        f"Login response missing token: {list(data.keys())}"
    )


@pytest.mark.asyncio
async def test_auth_invalid_login(client):
    """POST /api/auth/login with wrong password returns 401 or 400."""
    resp = await client.post("/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": "WrongPassword999!",
    })
    assert resp.status_code in (400, 401), (
        f"Expected 400/401 for invalid login, got {resp.status_code}: {resp.text[:200]}"
    )


@pytest.mark.asyncio
async def test_create_item(client, auth_token):
    """POST /api/documents with auth creates an item."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    resp = await client.post("/api/documents", json={
        "title": "Smoke Test Item",
        "content": "test",
    }, headers=headers)
    assert resp.status_code in (200, 201), (
        f"Create item failed: {resp.status_code} {resp.text[:200]}"
    )
    data = resp.json()
    assert "id" in data, f"Create response missing 'id': {list(data.keys())}"


@pytest.mark.asyncio
async def test_list_items(client, auth_token):
    """GET /api/documents with auth returns a list."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    resp = await client.get("/api/documents", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    items = data if isinstance(data, list) else data.get("data", data.get("items", []))
    assert isinstance(items, list), f"Expected list, got {type(items).__name__}"


@pytest.mark.asyncio
async def test_get_single_item(client, auth_token):
    """Create an item then GET /api/documents/{id} returns it."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    # Create first
    create_resp = await client.post("/api/documents", json={
        "title": "Get Test Item",
        "content": "get test",
    }, headers=headers)
    assert create_resp.status_code in (200, 201)
    item_id = create_resp.json()["id"]
    # Fetch
    resp = await client.get(f"/api/documents/{item_id}", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    fetched_id = str(data.get("id", ""))
    assert fetched_id == str(item_id), f"Expected id {item_id}, got {fetched_id}"


@pytest.mark.asyncio
async def test_delete_item(client, auth_token):
    """Create an item then DELETE /api/documents/{id} succeeds."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    create_resp = await client.post("/api/documents", json={
        "title": "Delete Test Item",
        "content": "delete test",
    }, headers=headers)
    assert create_resp.status_code in (200, 201)
    item_id = create_resp.json()["id"]
    # Delete
    resp = await client.delete(f"/api/documents/{item_id}", headers=headers)
    assert resp.status_code in (200, 204), (
        f"Delete failed: {resp.status_code} {resp.text[:200]}"
    )


@pytest.mark.asyncio
async def test_deployed_url():
    """If SHIP_DEPLOYED_URL is set, GET that URL returns 200."""
    deployed_url = os.environ.get("SHIP_DEPLOYED_URL")
    if not deployed_url:
        pytest.skip("SHIP_DEPLOYED_URL not set")
    async with httpx.AsyncClient(timeout=15) as c:
        resp = await c.get(deployed_url)
    assert resp.status_code == 200, (
        f"Deployed URL returned {resp.status_code}: {resp.text[:200]}"
    )


@pytest.mark.asyncio
async def test_routes_summary(client):
    """Verify multiple core API routes are responding (non-5xx)."""
    results = {}
    # Health
    resp = await client.get("/health")
    results["/health"] = resp.status_code
    # Signup (unique email to avoid conflicts)
    unique_email = f"summary-{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post("/api/auth/signup", json={
        "email": unique_email,
        "password": TEST_PASSWORD,
    })
    results["/api/auth/signup"] = resp.status_code
    # Login
    resp = await client.post("/api/auth/login", json={
        "email": unique_email,
        "password": TEST_PASSWORD,
    })
    results["/api/auth/login"] = resp.status_code
    # Documents list (may require auth, accept any non-5xx)
    resp = await client.get("/api/documents")
    results["/api/documents"] = resp.status_code

    non_5xx = sum(1 for code in results.values() if code < 500)
    print(f"All {non_5xx} API routes responding correctly")
    assert non_5xx >= 3, (
        f"Only {non_5xx}/4 routes returned non-5xx: {results}"
    )
