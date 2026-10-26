"""Imports every ORM module so Base.metadata is complete (Alembic, tests)."""

from asseta.core import audit, idempotency, outbox  # noqa: F401
from asseta.modules.accountability import models as accountability_models  # noqa: F401
from asseta.modules.expenses import models as expenses_models  # noqa: F401
from asseta.modules.finance import custody_models as finance_custody_models  # noqa: F401
from asseta.modules.finance import deposit_models as finance_deposit_models  # noqa: F401
from asseta.modules.finance import models as finance_models  # noqa: F401
from asseta.modules.fleet import models as fleet_models  # noqa: F401
from asseta.modules.fleet import photos as fleet_photos  # noqa: F401
from asseta.modules.geospatial import models as geospatial_models  # noqa: F401
from asseta.modules.hours import models as hours_models  # noqa: F401
from asseta.modules.identity import models as identity_models  # noqa: F401
from asseta.modules.intelligence import ml_models as intelligence_ml_models  # noqa: F401
from asseta.modules.intelligence import ml_monitoring_models as intelligence_ml_monitoring  # noqa: F401
from asseta.modules.intelligence import models as intelligence_models  # noqa: F401
from asseta.modules.jobs import models as jobs_models  # noqa: F401
from asseta.modules.managed_service import models as managed_service_models  # noqa: F401
from asseta.modules.meter import engine_models as meter_engine_models  # noqa: F401
from asseta.modules.meter import models as meter_models  # noqa: F401
from asseta.modules.notification import channel_models as notification_channel_models  # noqa: F401
from asseta.modules.notification import models as notification_models  # noqa: F401
from asseta.modules.platform_billing import models_catalog, models_commercial, models_ledger  # noqa: F401
from asseta.modules.policy import models as policy_models  # noqa: F401
from asseta.modules.sync import models as sync_models  # noqa: F401
from asseta.modules.telemetry import models as telemetry_models  # noqa: F401
from asseta.modules.tenancy import models as tenancy_models  # noqa: F401
from asseta.modules.tracker import models as tracker_models  # noqa: F401
