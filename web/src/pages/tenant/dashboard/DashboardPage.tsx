import Refresh from '@mui/icons-material/Refresh';
import { Button, Stack } from '@mui/material';
import { useCallback } from 'react';
import { overviewService } from '../../../api/services/overviewService';
import type { TenantOverviewDto } from '../../../api/types';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useInterval } from '../../../hooks/useInterval';
import { useNow } from '../../../hooks/useNow';
import { useLiveRefresh } from '../../../realtime/hooks';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { DASHBOARD_LIVE_ENTITIES } from './dashboardModel';
import {
  FleetSection,
  MoneySection,
  RiskSection,
  WorkSection,
  type Can,
} from './DashboardSections';

/** Fallback refresh while live updates are unavailable. */
const DASHBOARD_REFRESH_MS = 5 * 60_000;

export function DashboardContent({
  data,
  can,
  nowMs,
}: {
  data: TenantOverviewDto;
  can: Can;
  nowMs: number;
}) {
  const tz = data.timezone;
  const shared = { can, nowMs, timeZone: tz };
  if (data.fleet === null && data.work === null && data.money === null && data.risk === null) {
    return (
      <EmptyState
        title="Nothing to summarise for your role"
        description="The dashboard shows fleet, work, money and risk figures you may view."
      />
    );
  }
  return (
    <Stack spacing={4}>
      {data.fleet !== null && <FleetSection data={data.fleet} {...shared} />}
      {data.work !== null && <WorkSection data={data.work} {...shared} />}
      {data.money !== null && <MoneySection data={data.money} {...shared} />}
      {data.risk !== null && <RiskSection data={data.risk} {...shared} />}
    </Stack>
  );
}

/**
 * Tenant dashboard (`GET /tenant/overview`): the sections the caller may see, each figure linking to
 * its filtered list, with per-section freshness; refreshed live when the underlying records change.
 */
export function DashboardPage() {
  const { hasPermission } = useSession();
  const nowMs = useNow(60_000);
  const load = useCallback((signal: AbortSignal) => overviewService.get(signal), []);
  const overview = useAsyncResource(load);
  useLiveRefresh(DASHBOARD_LIVE_ENTITIES, overview.reload, { debounceMs: 5_000 });
  useInterval(overview.reload, DASHBOARD_REFRESH_MS);
  const data = overview.data;
  const can: Can = (permission) => hasPermission(permission);
  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle={
          data === null
            ? 'Fleet, work, money and risk at a glance'
            : `As of ${formatInstantIn(data.as_of, data.timezone)} · times in ${data.timezone}`
        }
        actions={
          <Button
            startIcon={<Refresh />}
            variant="outlined"
            onClick={overview.reload}
            loading={overview.loading && data !== null}
          >
            Refresh
          </Button>
        }
      />
      <AsyncContent
        resource={overview}
        errorTitle="Could not load the dashboard"
        loadingLabel="Loading dashboard"
      >
        {(d) => <DashboardContent data={d} can={can} nowMs={nowMs} />}
      </AsyncContent>
    </>
  );
}
