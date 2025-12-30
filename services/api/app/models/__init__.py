# Models package

# ==================== Legacy models (core system) ====================
from .legacy import (
    KUType, RelationType,
    SourceDocument, ExtractedText, KnowledgeUnit, KUReview,
    Conversation, Feedback, ScenarioPrompt, DQRun, PipelineRun,
    KURelation, Product, DedupGroup,
)

# ==================== New models (frontend system) ====================
from .user import User, Role, UserSession
from .conversation import ConversationV2, ConversationMessage, ConversationShare
from .config import ScenarioConfig, PromptTemplate, PromptHistory, KUTypeDefinition
from .settings import SystemConfig, ConfigChangeLog, ConfigEnvMapping
from .llm import LLMProvider, LLMModel, LLMModelAssignment
from .contribution import Contribution, ContributionStats, CitationRecord
from .task import CollaborationTask

__all__ = [
    # Legacy - Constants
    "KUType", "RelationType",
    # Legacy - Core models
    "SourceDocument", "ExtractedText", "KnowledgeUnit", "KUReview",
    "Conversation", "Feedback", "ScenarioPrompt", "DQRun", "PipelineRun",
    "KURelation", "Product", "DedupGroup",
    # User
    "User", "Role", "UserSession",
    # Conversation (new)
    "ConversationV2", "ConversationMessage", "ConversationShare",
    # Config
    "ScenarioConfig", "PromptTemplate", "PromptHistory", "KUTypeDefinition",
    # Settings
    "SystemConfig", "ConfigChangeLog", "ConfigEnvMapping",
    # LLM
    "LLMProvider", "LLMModel", "LLMModelAssignment",
    # Contribution
    "Contribution", "ContributionStats", "CitationRecord",
    # Task
    "CollaborationTask",
]

