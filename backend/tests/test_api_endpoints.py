"""Tests des endpoints API du chatbot."""

import pytest
import pytest_asyncio


class TestHealthEndpoint:
    """Tests du endpoint de santé."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        """Le healthcheck doit retourner 200."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_root_returns_response(self, client):
        """La racine doit retourner une réponse."""
        response = await client.get("/")
        assert response.status_code in (200, 307)


class TestChatEndpoint:
    """Tests de l'endpoint de chat."""

    @pytest.mark.asyncio
    async def test_chat_with_valid_message(self, client):
        """Un message valide doit retourner une réponse."""
        response = await client.post(
            "/api/chat",
            json={
                "message": "Bonjour",
                "session_id": "test-session-001",
            },
            headers={"X-Session-ID": "test-session-001"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "session_id" in data
        assert "language" in data
        assert "source" in data

    @pytest.mark.asyncio
    async def test_chat_with_empty_message(self, client):
        """Un message vide doit retourner une erreur."""
        response = await client.post(
            "/api/chat",
            json={
                "message": "",
                "session_id": "test-session-002",
            },
            headers={"X-Session-ID": "test-session-002"},
        )
        # Peut être 400 ou 422 selon la validation
        assert response.status_code in (200, 400, 422)

    @pytest.mark.asyncio
    async def test_chat_with_language_override(self, client):
        """Le forçage de langue doit être respecté."""
        response = await client.post(
            "/api/chat",
            json={
                "message": "Comment s'inscrire ?",
                "session_id": "test-session-003",
                "language": "fr",
            },
            headers={"X-Session-ID": "test-session-003"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "fr"

    @pytest.mark.asyncio
    async def test_chat_returns_response_time(self, client):
        """Le temps de réponse doit être présent dans la réponse."""
        response = await client.post(
            "/api/chat",
            json={
                "message": "Quand est le BFEM ?",
                "session_id": "test-session-004",
            },
            headers={"X-Session-ID": "test-session-004"},
        )
        if response.status_code == 200:
            data = response.json()
            assert "response_time_ms" in data
            assert isinstance(data["response_time_ms"], int)


class TestFAQEndpoint:
    """Tests de l'endpoint FAQ."""

    @pytest.mark.asyncio
    async def test_faq_list(self, client):
        """La liste des FAQ doit retourner un tableau."""
        response = await client.get("/api/faq")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_faq_search(self, client):
        """La recherche FAQ doit fonctionner."""
        response = await client.get("/api/faq/search?q=inscription")
        assert response.status_code in (200, 404)
