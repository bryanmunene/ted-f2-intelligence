from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class TimingConfig(BaseModel):
    min_days_to_deadline: int = 3
    exclude_after_days_since_publication: int = 90
    expiring_soon_days: int = 7
    missing_deadline_penalty: int = 18
    missing_publication_date_penalty: int = 10
    stale_publication_penalty: int = 20
    short_deadline_penalty: int = 22
    viable_timing_bonus: int = 6


class KeywordTerm(BaseModel):
    text: str
    aliases: list[str] = Field(default_factory=list)
    scope: Literal["all", "title", "summary", "buyer", "metadata"] = "all"
    weight_delta: int = 0
    requires_all: list[str] = Field(default_factory=list)
    match_mode: Literal["phrase", "contains", "acronym"] = "phrase"


class PositiveKeywordGroup(BaseModel):
    id: str
    name: str
    weight: int
    extra_match_weight: int = 0
    max_score: int | None = None
    title_match_bonus: int = 0
    terms: list[str | KeywordTerm] = Field(default_factory=list)

    def materialized_terms(self) -> list[KeywordTerm]:
        return [term if isinstance(term, KeywordTerm) else KeywordTerm(text=term) for term in self.terms]


class NegativeKeywordGroup(BaseModel):
    id: str
    name: str
    penalty: int
    extra_match_penalty: int = 0
    max_penalty: int | None = None
    title_match_bonus: int = 0
    terms: list[str | KeywordTerm] = Field(default_factory=list)

    def materialized_terms(self) -> list[KeywordTerm]:
        return [term if isinstance(term, KeywordTerm) else KeywordTerm(text=term) for term in self.terms]


class PlatformSignal(BaseModel):
    id: str
    name: str
    terms: list[str | KeywordTerm] = Field(default_factory=list)
    penalty: int = 0
    bonus: int = 0
    severe: bool = False

    def materialized_terms(self) -> list[KeywordTerm]:
        return [term if isinstance(term, KeywordTerm) else KeywordTerm(text=term) for term in self.terms]


class PlatformSignals(BaseModel):
    hard_lock: list[PlatformSignal] = Field(default_factory=list)
    soft_lock: list[PlatformSignal] = Field(default_factory=list)
    openness: list[PlatformSignal] = Field(default_factory=list)


class QualificationQuestions(BaseModel):
    default: list[str] = Field(default_factory=list)
    missing_deadline: list[str] = Field(default_factory=list)
    hard_lock: list[str] = Field(default_factory=list)
    soft_lock: list[str] = Field(default_factory=list)
    integration: list[str] = Field(default_factory=list)
    timing: list[str] = Field(default_factory=list)


class StrategicWeighting(BaseModel):
    preferred_countries: dict[str, int] = Field(default_factory=dict)
    preferred_buyer_keywords: dict[str, int] = Field(default_factory=dict)
    preferred_sector_keywords: dict[str, int] = Field(default_factory=dict)
    deprioritized_cpv_prefixes: list[str] = Field(default_factory=list)
    deprioritization_penalty: int = 0


class KeywordComboRule(BaseModel):
    id: str
    name: str
    group_ids: list[str] = Field(default_factory=list)
    bonus: int


class KeywordPack(BaseModel):
    version: str
    timing: TimingConfig
    positive_groups: list[PositiveKeywordGroup] = Field(default_factory=list)
    negative_groups: list[NegativeKeywordGroup] = Field(default_factory=list)
    combo_rules: list[KeywordComboRule] = Field(default_factory=list)
    platform_signals: PlatformSignals = Field(default_factory=PlatformSignals)
    qualification_questions: QualificationQuestions = Field(default_factory=QualificationQuestions)
    strategic_weighting: StrategicWeighting = Field(default_factory=StrategicWeighting)

    def positive_group_map(self) -> dict[str, PositiveKeywordGroup]:
        return {group.id: group for group in self.positive_groups}

    def negative_group_map(self) -> dict[str, NegativeKeywordGroup]:
        return {group.id: group for group in self.negative_groups}


class SearchProfile(BaseModel):
    name: str
    slug: str
    description: str
    keyword_group_ids: list[str] = Field(default_factory=list)
    negative_group_ids: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)
    hard_lock_penalty_multiplier: float = 1.0
    soft_lock_penalty_multiplier: float = 1.0
    openness_bonus_multiplier: float = 1.0
    country_bias: dict[str, int] = Field(default_factory=dict)


class SearchProfileRegistry(BaseModel):
    profiles: list[SearchProfile] = Field(default_factory=list)

    def by_name(self, name: str | None) -> SearchProfile:
        if not self.profiles:
            raise ValueError("No search profiles configured.")
        if not name:
            return self.profiles[0]
        for profile in self.profiles:
            if profile.name == name or profile.slug == name:
                return profile
        raise KeyError(f"Unknown search profile: {name}")

    @property
    def names(self) -> list[str]:
        return [profile.name for profile in self.profiles]


class TenderChecklistItem(BaseModel):
    id: str
    label: str


class TenderChecklistTemplate(BaseModel):
    name: str
    version: str
    source_document: str | None = None
    items: list[TenderChecklistItem] = Field(default_factory=list)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    env: str = "development"
    name: str = "cBrain TED F2 Intelligence"
    secret_key: str = "change-me"
    log_level: str = "INFO"
    auth_enabled: bool = False
    default_user_email: str = "f2-intelligence@cbrain.com"
    default_user_name: str = "Internal Analyst"
    header_auth_email_header: str = "X-Forwarded-Email"
    header_auth_name_header: str = "X-Forwarded-User"
    session_cookie_name: str = "cbrain_ted_session"
    session_https_only: bool = False
    session_max_age_seconds: int = 8 * 60 * 60
    ui_timezone: str = "Europe/Copenhagen"
    database_url: str = "sqlite+pysqlite:///./ted_app.db"
    sqlalchemy_echo: bool = False
    auto_create_schema: bool = True
    ted_api_base_url: str = "https://api.ted.europa.eu"
    ted_search_path: str = "/v3/notices/search"
    ted_request_timeout_seconds: int = 30
    ted_retry_attempts: int = 4
    ted_requests_per_minute: int = 60
    ted_cache_ttl_seconds: int = 300
    ted_default_page_size: int = 50
    ted_max_page_size: int = 250
    ted_max_pages_per_scan: int = 4
    ted_search_scope: str = "ACTIVE"
    keyword_pack_path: Path = Path("config/keyword_pack.yaml")
    search_profiles_path: Path = Path("config/search_profiles.yaml")
    tender_checklist_template_path: Path = Path("config/tender_checklist.yaml")
    scoring_version: str = "2026.03.2"
    analysis_extraction_version: str = "2026.03.2"

    @property
    def project_root(self) -> Path:
        return BASE_DIR

    @property
    def resolved_keyword_pack_path(self) -> Path:
        return self._resolve_path(self.keyword_pack_path)

    @property
    def resolved_search_profiles_path(self) -> Path:
        return self._resolve_path(self.search_profiles_path)

    @property
    def resolved_tender_checklist_template_path(self) -> Path:
        return self._resolve_path(self.tender_checklist_template_path)

    @property
    def templates_dir(self) -> Path:
        return self.project_root / "app" / "templates"

    @property
    def static_dir(self) -> Path:
        return self.project_root / "app" / "static"

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    def _resolve_path(self, raw_path: Path) -> Path:
        return raw_path if raw_path.is_absolute() else self.project_root / raw_path


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML payload in {path} must be a mapping.")
    return payload


def load_keyword_pack(path: Path) -> KeywordPack:
    return KeywordPack.model_validate(_read_yaml(path))


def load_search_profiles(path: Path) -> SearchProfileRegistry:
    return SearchProfileRegistry.model_validate(_read_yaml(path))


def load_tender_checklist_template(path: Path) -> TenderChecklistTemplate:
    return TenderChecklistTemplate.model_validate(_read_yaml(path))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
