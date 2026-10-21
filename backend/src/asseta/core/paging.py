"""Server-side pagination envelope shared by list endpoints."""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class PageParams(BaseModel):
    page: int
    page_size: int
    q: str | None
    sort: str | None


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[str | None, Query(max_length=64)] = None,
) -> PageParams:
    return PageParams(page=page, page_size=page_size, q=q, sort=sort)


def paginate[T](session: Session, stmt: Select[T], params: PageParams) -> tuple[list[T], int]:
    total = int(session.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one())
    rows = list(session.execute(stmt.limit(params.page_size).offset((params.page - 1) * params.page_size)).scalars())
    return rows, total


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
