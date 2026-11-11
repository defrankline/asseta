"""Data protection policy (DEC-032 Phase 5, guideline 6 and 9). Tenant configuration with safe platform defaults:
the scheduled balance verification is OFF until a tenant opts in; on-demand verification and data export are always
available to whoever holds the permission.

`company_deletion_waiting_days` is platform-wide (PLATFORM_ONLY_FIELDS): how long a company stays read-only after its
owner asks for it to be closed, before all its data is deleted. Only the platform owner changes it, by versioning the
platform default; a tenant cannot shorten or lengthen its own waiting period."""

from pydantic import BaseModel, ConfigDict, Field


class DataProtectionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    balance_verification_enabled: bool = False  # the scheduled sweep; on-demand runs are always allowed
    balance_verification_interval_days: int = Field(default=7, ge=1, le=90)
    data_export_retention_days: int = Field(default=7, ge=1, le=90)  # a finished export file is deleted after this
    company_deletion_waiting_days: int = Field(default=30, ge=1, le=365)  # platform-wide; see the module docstring


DATA_PROTECTION_SEED: dict[str, object] = {
    "balance_verification_enabled": False,
    "balance_verification_interval_days": 7,
    "data_export_retention_days": 7,
    "company_deletion_waiting_days": 30,
}
# Fields only the platform layer may set (a tenant version carrying one is refused).
DATA_PROTECTION_PLATFORM_ONLY = frozenset({"company_deletion_waiting_days"})
