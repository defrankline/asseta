"""Identity mirror tables. Keycloak is authoritative (DEC-005); these rows are synchronized copies used for
menus, audit attribution, request-time permission resolution and offline policy snapshots."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, Timestamps, UuidPk


class AppUser(UuidPk, Timestamps, Base):
    __tablename__ = "app_user"

    keycloak_subject: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Permission(UuidPk, Timestamps, Base):
    __tablename__ = "permission"

    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)  # PLATFORM | TENANT
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Menu(UuidPk, Timestamps, Base):
    __tablename__ = "menu"

    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    path: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    required_permission: Mapped[str] = mapped_column(String(128), nullable=False)


class Role(UuidPk, Timestamps, Base):
    """A Keycloak role group: `/platform/<key>` (tenant_id NULL) or `/tenants/<tenant_id>/<key>`."""

    __tablename__ = "role"
    __table_args__ = (UniqueConstraint("keycloak_group_path", name="uq_role_group_path"),)

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    keycloak_group_id: Mapped[str] = mapped_column(String(64), nullable=False)
    keycloak_group_path: Mapped[str] = mapped_column(String(300), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permission"

    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("role.id", ondelete="CASCADE"), primary_key=True)
    permission_code: Mapped[str] = mapped_column(ForeignKey("permission.code", ondelete="CASCADE"), primary_key=True)


class TenantMembership(UuidPk, Timestamps, Base):
    """Effective-dated membership mirror, refreshed from Keycloak group membership."""

    __tablename__ = "tenant_membership"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "role_id", name="uq_membership"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("role.id", ondelete="CASCADE"), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoleTemplateGrant(Base):
    """Which template permissions have been offered to a Keycloak role group (once offered, an owner's later
    removal is respected; permissions introduced by new releases are offered exactly once)."""

    __tablename__ = "role_template_grant"

    group_path: Mapped[str] = mapped_column(String(300), primary_key=True)
    permission_code: Mapped[str] = mapped_column(String(128), primary_key=True)
    offered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
