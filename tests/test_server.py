"""
Functional tests for the Novel Read server.

These exercise every endpoint group (system, auth, novels, chapters, rules,
rankings, search, AI) plus the configuration loader. Network-dependent
operations (live search / ranking fetch / AI calls) are exercised but are
tolerant of network failures since the sandbox may be offline.
"""

import base64

from server.core.config import settings

API_KEY = settings.api_key
AUTH_HEADERS = {"X-API-Key": API_KEY}


# ---------------------------------------------------------------------------
# System / health
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_info(client):
    r = client.get("/api/info")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Novel Read API"
    assert "channels" in body
    assert "ai" in body


def test_stats_empty(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert body == {"novels": 0, "chapters": 0, "rules": 0, "rankings": 0}


def test_openapi_schema(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "Novel Read API"
    # Make sure our key paths are registered
    paths = schema["paths"]
    assert "/health" in paths
    assert "/api/novels" in paths
    assert "/api/ai/captcha" in paths


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_auth_token_success(client):
    r = client.post("/api/auth/token", json={"api_key": API_KEY})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0


def test_auth_token_bad_key(client):
    r = client.post("/api/auth/token", json={"api_key": "wrong-key"})
    assert r.status_code == 401


def test_auth_verify_token(client):
    token = client.post("/api/auth/token", json={"api_key": API_KEY}).json()["access_token"]
    r = client.get("/api/auth/verify", params={"token": token})
    assert r.status_code == 200
    assert r.json()["valid"] is True


def test_auth_verify_invalid_token(client):
    r = client.get("/api/auth/verify", params={"token": "not-a-jwt"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Novels (auth-gated writes)
# ---------------------------------------------------------------------------

def test_create_novel_requires_api_key(client):
    r = client.post("/api/novels", json={"title": "Test Novel"})
    assert r.status_code == 401


def test_create_and_get_novel(client):
    payload = {
        "title": "三体",
        "author": "刘慈欣",
        "description": "科幻小说",
        "source": "manual",
        "status": "completed",
    }
    r = client.post("/api/novels", json=payload, headers=AUTH_HEADERS)
    assert r.status_code == 201, r.text
    created = r.json()
    novel_id = created["id"]
    assert created["title"] == "三体"
    assert created["author"] == "刘慈欣"

    # GET by id
    r = client.get(f"/api/novels/{novel_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "三体"

    # GET 404
    r = client.get("/api/novels/99999")
    assert r.status_code == 404


def test_list_novels_with_query(client):
    # seed two novels
    for title in ("斗破苍穹", "斗罗大陆", "遮天"):
        client.post(
            "/api/novels",
            json={"title": title, "author": "Author " + title},
            headers=AUTH_HEADERS,
        )

    r = client.get("/api/novels")
    assert r.status_code == 200
    assert len(r.json()) == 3

    # search by title substring
    r = client.get("/api/novels", params={"q": "斗"})
    assert r.status_code == 200
    titles = [n["title"] for n in r.json()]
    assert "斗破苍穹" in titles
    assert "斗罗大陆" in titles
    assert "遮天" not in titles


def test_delete_novel(client):
    novel_id = client.post(
        "/api/novels", json={"title": "To Delete"}, headers=AUTH_HEADERS
    ).json()["id"]

    r = client.delete(f"/api/novels/{novel_id}", headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert client.get(f"/api/novels/{novel_id}").status_code == 404


def test_delete_novel_requires_auth(client):
    novel_id = client.post(
        "/api/novels", json={"title": "X"}, headers=AUTH_HEADERS
    ).json()["id"]
    assert client.delete(f"/api/novels/{novel_id}").status_code == 401


# ---------------------------------------------------------------------------
# Chapters
# ---------------------------------------------------------------------------

def _make_novel(client):
    return client.post(
        "/api/novels", json={"title": "Novel"}, headers=AUTH_HEADERS
    ).json()["id"]


def test_add_and_list_chapter(client):
    novel_id = _make_novel(client)

    r = client.post(
        f"/api/novels/{novel_id}/chapters",
        json={"title": "第一章", "content": "内容内容内容", "chapter_number": 1},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 201, r.text
    chapter = r.json()
    assert chapter["title"] == "第一章"
    assert chapter["novel_id"] == novel_id

    # chapters_count should be incremented
    novel = client.get(f"/api/novels/{novel_id}").json()
    assert novel["chapters_count"] == 1

    # list
    r = client.get(f"/api/novels/{novel_id}/chapters")
    assert r.status_code == 200
    assert len(r.json()) == 1

    # detail
    r = client.get(f"/api/chapters/{chapter['id']}")
    assert r.status_code == 200
    assert r.json()["content"] == "内容内容内容"


def test_add_chapter_requires_auth(client):
    novel_id = _make_novel(client)
    r = client.post(
        f"/api/novels/{novel_id}/chapters",
        json={"title": "t", "content": "c"},
    )
    assert r.status_code == 401


def test_chapters_for_unknown_novel_404(client):
    r = client.get("/api/novels/99999/chapters")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Source rules
# ---------------------------------------------------------------------------

def test_create_and_list_rule(client):
    r = client.post(
        "/api/rules",
        json={"domain": "example.com", "name": "Example", "rules_json": "{}"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 201, r.text
    rule_id = r.json()["id"]

    r = client.get("/api/rules")
    assert r.status_code == 200
    assert any(rule["id"] == rule_id for rule in r.json())

    # filter by active
    r = client.get("/api/rules", params={"active": True})
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_create_rule_requires_auth(client):
    r = client.post("/api/rules", json={"domain": "x.com"})
    assert r.status_code == 401


def test_create_rule_duplicate_domain(client):
    client.post(
        "/api/rules", json={"domain": "dup.com"}, headers=AUTH_HEADERS
    )
    r = client.post(
        "/api/rules", json={"domain": "dup.com"}, headers=AUTH_HEADERS
    )
    # domain is unique -> 400
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Rankings (DB list + live fetch tolerance)
# ---------------------------------------------------------------------------

def test_list_rankings_empty(client):
    r = client.get("/api/rankings")
    assert r.status_code == 200
    assert r.json() == []


def test_fetch_rankings_returns_list(client):
    # Live fetch may hit network; just ensure the endpoint returns a list and
    # does not 500.
    r = client.get("/api/rankings/fetch", params={"source": "tomato"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Search (tolerant of offline sandbox)
# ---------------------------------------------------------------------------

def test_search_returns_list(client):
    r = client.get("/api/search", params={"q": "三体"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_search_requires_query(client):
    r = client.get("/api/search")
    assert r.status_code == 422  # missing required param


def test_search_opensource(client):
    r = client.get("/api/search/opensource", params={"q": "三体"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# AI endpoints (no live API key -> fallback paths must still work)
# ---------------------------------------------------------------------------

def test_ai_status(client):
    r = client.get("/api/ai/status")
    assert r.status_code == 200
    body = r.json()
    assert "code_model" in body
    assert "vision_model" in body
    assert "captcha_solved_total" in body


def test_ai_generate_script_fallback(client):
    # No API key configured -> should return the fallback script template.
    r = client.post(
        "/api/ai/generate-script",
        json={"url": "https://example.com", "html_sample": "<html></html>"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "script" in body
    assert isinstance(body["script"], str)
    assert len(body["script"]) > 0
    assert body["model_configured"] is False


def test_ai_fix_script_fallback(client):
    r = client.post(
        "/api/ai/fix-script",
        json={"script": "def x(): pass", "error_message": "boom"},
    )
    assert r.status_code == 200
    # Without a configured model the original script is returned unchanged.
    assert r.json()["script"] == "def x(): pass"


def test_ai_analyze_image_fallback(client):
    img_b64 = base64.b64encode(b"fake-image-bytes").decode()
    r = client.post(
        "/api/ai/analyze-image",
        json={"image_base64": img_b64, "prompt": "describe"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "description" in body
    assert "bytes" in body["description"]  # fallback mentions image size


def test_ai_analyze_image_bad_base64(client):
    r = client.post(
        "/api/ai/analyze-image",
        json={"image_base64": "!!!not-base64!!!", "prompt": "x"},
    )
    assert r.status_code == 400


def test_ai_captcha_fallback(client):
    img_b64 = base64.b64encode(b"fake-captcha").decode()
    r = client.post(
        "/api/ai/captcha",
        json={"image_base64": img_b64, "captcha_type": "text"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "text"
    assert "success" in body
