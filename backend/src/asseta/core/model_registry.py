"""Imports every ORM module so Base.metadata is complete (Alembic, tests)."""

from asseta.core import audit, idempotency, outbox  # noqa: F401
from asseta.modules.fleet import models as fleet_models  # noqa: F401
from asseta.modules.fleet import photos as fleet_photos  # noqa: F401
from asseta.modules.geospatial import models as geospatial_models  # noqa: F401
from asseta.modules.identity import models as identity_models  # noqa: F401
from asseta.modules.jobs import models as jobs_models  # noqa: F401
from asseta.modules.meter import models as meter_models  # noqa: F401
from asseta.modules.platform_billing import models_commercial, models_ledger  # noqa: F401
from asseta.modules.policy import models as policy_models  # noqa: F401
from asseta.modules.telemetry import models as telemetry_models  # noqa: F401
from asseta.modules.tenancy import models as tenancy_models  # noqa: F401
from asseta.modules.tracker import models as tracker_models  # noqa: F401
