"""Contrato JSON de la API HTTP (compatible con la versión anterior)."""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    max_results: int = Field(default=5, ge=1, le=20)
    search_depth: Literal["basic", "advanced"] = "basic"
    topic: Literal["general", "news"] = "general"
    time_range: Literal["day", "week", "month", "year"] | None = None
    domains: list[str] = Field(default_factory=list, max_length=10)
    exclude_domains: list[str] = Field(default_factory=list, max_length=10)
    include_raw_content: bool = False

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("domains", "exclude_domains")
    @classmethod
    def normalize_domains(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            domain = value.strip().lower().removeprefix("www.")
            if domain and domain not in cleaned and " " not in domain and "/" not in domain:
                cleaned.append(domain)
        return cleaned


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    content: str = ""
    score: float = Field(default=0.0, ge=0.0)
    published_date: str | None = None
    raw_content: str | None = None


class SearchResponse(BaseModel):
    query: str
    answer: str | None = None
    results: list[SearchResult]
    response_time: float = Field(ge=0.0)
    provider: str
    warnings: list[str] = Field(default_factory=list)


class ExtractRequest(BaseModel):
    urls: list[HttpUrl] = Field(min_length=1, max_length=20)


class ExtractedPage(BaseModel):
    url: HttpUrl
    title: str | None = None
    content: str
    content_type: str | None = None
    truncated: bool = False


class ExtractResponse(BaseModel):
    results: list[ExtractedPage]
    failed_results: list[dict[str, str]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "CuySearch"
    version: str

