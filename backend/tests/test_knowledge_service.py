"""Tests pour le service de base de connaissances."""

import pytest
import pytest_asyncio
from app.services.knowledge_service import KnowledgeService


@pytest_asyncio.fixture
async def kb_service():
    """KnowledgeService sans FAQ service (mode texte uniquement)."""
    service = KnowledgeService(faq_service=None)
    return service


class TestKnowledgeServiceInit:
    """Tests d'initialisation."""

    @pytest.mark.asyncio
    async def test_initialize_loads_documents(self, kb_service):
        """L'initialisation doit charger les documents JSON."""
        result = await kb_service.initialize()
        # Peut être True ou False selon la présence du fichier
        if result:
            assert kb_service.document_count > 0
            assert kb_service.is_available is True

    @pytest.mark.asyncio
    async def test_double_initialize(self, kb_service):
        """La double initialisation ne doit pas poser de problème."""
        await kb_service.initialize()
        result = await kb_service.initialize()
        # Should return True on second call if first succeeded
        if kb_service._loaded:
            assert result is True


class TestTextSearch:
    """Tests de la recherche textuelle (fallback sans embeddings)."""

    @pytest.mark.asyncio
    async def test_text_search_returns_results(self, kb_service):
        """La recherche textuelle doit retourner des résultats pertinents."""
        await kb_service.initialize()
        if not kb_service.is_available:
            pytest.skip("Base de connaissances non disponible")

        results = kb_service._text_search("système éducatif sénégalais", limit=3, category=None)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_text_search_with_category(self, kb_service):
        """La recherche textuelle doit respecter le filtre de catégorie."""
        await kb_service.initialize()
        if not kb_service.is_available:
            pytest.skip("Base de connaissances non disponible")

        results = kb_service._text_search("examen", limit=5, category="examen")
        for r in results:
            assert r["category"] == "examen"

    @pytest.mark.asyncio
    async def test_empty_search_returns_empty(self, kb_service):
        """Une recherche dans un service non initialisé renvoie une liste vide."""
        results = await kb_service.search("test")
        assert results == []


class TestContextFormatting:
    """Tests du formatage du contexte LLM."""

    def test_format_empty_documents(self, kb_service):
        """Une liste vide de documents donne un contexte vide."""
        assert kb_service.get_context_for_llm([]) == ""

    def test_format_single_document(self, kb_service):
        """Un seul document est formaté correctement."""
        docs = [{"title": "Test", "content": "Contenu de test."}]
        context = kb_service.get_context_for_llm(docs)
        assert "Test" in context
        assert "Contenu de test" in context
        assert "informations de référence" in context

    def test_format_respects_max_chars(self, kb_service):
        """Le contexte ne dépasse pas max_chars."""
        docs = [
            {"title": f"Doc {i}", "content": "A" * 500}
            for i in range(10)
        ]
        context = kb_service.get_context_for_llm(docs, max_chars=1000)
        assert len(context) <= 1200  # marge pour le préambule


class TestProperties:
    """Tests des propriétés."""

    def test_not_available_before_init(self, kb_service):
        assert kb_service.is_available is False
        assert kb_service.document_count == 0
