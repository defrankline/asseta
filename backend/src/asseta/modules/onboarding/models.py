"""Go-live setup checklist: the only things it stores are the owner's own choices (a step marked "not needed", the
"the default controls are fine" confirmation, the checklist dismissed). Every step's progress is computed live from the
tenant's data. Append-only (DB guard trigger): the current choice is the latest row per step/kind; undoing appends."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Identity, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow


class SetupChoiceAction(StrEnum):
    STEP_NOT_NEEDED = "STEP_NOT_NEEDED"  # the owner says this step does not apply to the business (with a reason)
    STEP_NEEDED = "STEP_NEEDED"  # undoes STEP_NOT_NEEDED
    CONTROLS_CONFIRMED = "CONTROLS_CONFIRMED"  # "the platform default controls are fine for us"
    DISMISSED = "DISMISSED"  # hide the go-live banner
    UNDISMISSED = "UNDISMISSED"  # show it again


class TenantSetupChoice(UuidPk, Base):
    __tablename__ = "tenant_setup_choice"
    __table_args__ = (Index("ix_tenant_setup_choice_tenant_seq", "tenant_id", "seq"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)  # append order (latest wins)
    action: Mapped[SetupChoiceAction] = mapped_column(
        Enum(SetupChoiceAction, native_enum=False, length=24), nullable=False
    )
    step_key: Mapped[str | None] = mapped_column(String(40))  # set for STEP_NOT_NEEDED / STEP_NEEDED
    reason: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
