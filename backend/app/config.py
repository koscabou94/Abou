"""
Configuration de l'application via variables d'environnement.
"""

from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):

    # === Base de données ===
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./edu_chatbot.db",
        description="URL de connexion à la base de données"
    )

    # === Redis (cache, optionnel) ===
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="URL Redis (laisser vide pour désactiver)"
    )

    # === Sécurité ===
    SECRET_KEY: str = Field(
        default="changez-cette-cle-secrete-en-production",
        description="Clé secrète pour la signature des tokens JWT"
    )
    API_KEY: str = Field(
        default="admin-api-key-changez-en-production",
        description="Clé API pour les endpoints d'administration"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24)

    # === Groq LLM ===
    GROQ_API_KEY: str = Field(
        default="",
        description="Clé API Groq (https://console.groq.com)"
    )
    LLM_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Modèle Groq à utiliser"
    )

    # === Paramètres LLM ===
    MAX_TOKENS: int = Field(default=800)
    TEMPERATURE: float = Field(default=0.3)
    CONTEXT_WINDOW: int = Field(default=5)

    # === Langues supportées ===
    SUPPORTED_LANGUAGES: List[str] = Field(default=["fr", "wo", "ff", "ar"])
    PIVOT_LANGUAGE: str = Field(default="fr")

    # === Mode allégé (sans Redis) ===
    USE_LIGHTWEIGHT_MODE: bool = Field(
        default=True,
        description="Mode cloud : sans Redis, traduction désactivée"
    )

    # === Serveur ===
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    DEBUG: bool = Field(default=False)
    WORKERS: int = Field(default=1)

    # === CORS ===
    CORS_ORIGINS: List[str] = Field(
        default=["*"],
        description="Origines autorisées pour les requêtes CORS"
    )

    # === FAQ ===
    FAQ_MATCH_THRESHOLD: float = Field(default=0.30)
    FAQ_HIGH_CONFIDENCE_THRESHOLD: float = Field(default=0.55)

    # === Cache ===
    CACHE_TTL_SECONDS: int = Field(default=3600)

    # === Limites de débit ===
    RATE_LIMIT_CHAT: str = Field(default="20/minute")
    RATE_LIMIT_FAQ: str = Field(default="100/minute")

    # === Chemins des données ===
    @property
    def FAQ_DATA_PATH(self) -> str:
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_root = os.path.dirname(base_dir)
        return os.path.join(project_root, "data", "faq_senegal.json")

    @property
    def KNOWLEDGE_BASE_PATH(self) -> str:
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_root = os.path.dirname(base_dir)
        return os.path.join(project_root, "data", "knowledge_base.json")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
