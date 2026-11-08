"""Data protection policy (DEC-032 Phase 5, guideline 6 and 9). Tenant configuration with safe platform defaults:
the scheduled balance verification is OFF until a tenant opts in; on-demand verification and data export are always
available to whoever holds the permission."""

from pydantic import BaseModel, ConfigDict, Field


class DataProtectionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    balance_verification_enabled: bool = False  # the scheduled sweep; on-demand runs are always allowed
    balance_verification_interval_days: int = Field(default=7, ge=1, le=90)
    data_export_retention_days: int = Field(default=7, ge=1, le=90)  # a finished export file is deleted after this


DATA_PROTECTION_SEED: dict[str, object] = {
    "balance_verification_enabled": False,
    "balance_verification_interval_days": 7,
    "data_export_retention_days": 7,
}
