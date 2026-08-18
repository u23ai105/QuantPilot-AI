import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_check(client):
    response = await client.get("/ready")
    # For now, it will return down since it's just testing without full services
    assert response.status_code == 200
    data = response.json()
    assert "db" in data
    assert "redis" in data
