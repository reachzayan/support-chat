from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.db import SessionDep
from app.models.article import KbArticle
from app.security.deps import CurrentAdmin, CurrentUser
from app.services.site_admin import AdminError, SiteAdminService

router = APIRouter()


class ArticleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    body: str


class ArticlePatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    body: str | None = None
    enabled: bool | None = None


class ArticleOut(BaseModel):
    id: UUID
    site_id: UUID
    title: str
    body: str
    enabled: bool
    updated_by: UUID | None


class ArticleListOut(BaseModel):
    items: list[ArticleOut]


def _http_error(exc: AdminError) -> HTTPException:
    if exc.code == "not_found":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if exc.code == "too_large":
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Too large")
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid request"
    )


def _article_out(article: KbArticle) -> ArticleOut:
    return ArticleOut(
        id=article.id,
        site_id=article.site_id,
        title=article.title,
        body=article.body,
        enabled=article.enabled,
        updated_by=article.updated_by,
    )


@router.get("/api/sites/{site_id}/articles", response_model=ArticleListOut)
async def list_articles(site_id: UUID, session: SessionDep, _staff: CurrentUser) -> ArticleListOut:
    try:
        rows = await SiteAdminService(session).list_articles(site_id)
    except AdminError as exc:
        raise _http_error(exc) from exc
    return ArticleListOut(items=[_article_out(row) for row in rows])


@router.post(
    "/api/sites/{site_id}/articles",
    response_model=ArticleOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_article(
    site_id: UUID, payload: ArticleIn, session: SessionDep, admin: CurrentAdmin
) -> ArticleOut:
    try:
        article = await SiteAdminService(session).create_article(
            site_id, admin, payload.title, payload.body
        )
    except AdminError as exc:
        raise _http_error(exc) from exc
    return _article_out(article)


@router.patch("/api/articles/{article_id}", response_model=ArticleOut)
async def patch_article(
    article_id: UUID, payload: ArticlePatchIn, session: SessionDep, admin: CurrentAdmin
) -> ArticleOut:
    try:
        article = await SiteAdminService(session).update_article(
            article_id,
            admin,
            title=payload.title,
            body=payload.body,
            enabled=payload.enabled,
        )
    except AdminError as exc:
        raise _http_error(exc) from exc
    return _article_out(article)
