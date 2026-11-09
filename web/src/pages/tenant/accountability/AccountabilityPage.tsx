import Refresh from '@mui/icons-material/Refresh';
import { Alert, Box, Button, Link, Typography } from '@mui/material';
import { useCallback, useId, useState } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router';
import { accountabilityService } from '../../../api/services/accountabilityService';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useInterval } from '../../../hooks/useInterval';
import { ROUTES } from '../../../navigation/routes';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { AccountabilityTiles } from './AccountabilityTiles';
import { DashboardPeriod, ManagementDashboard } from './management/ManagementDashboard';

const REFRESH_MS = 5 * 60_000;

function useSummary(from = '', to = '') {
  const load = useCallback(
    (signal: AbortSignal) =>
      accountabilityService.summary(
        signal,
        from === '' && to === ''
          ? undefined
          : { date_from: from || undefined, date_to: to || undefined },
      ),
    [from, to],
  );
  const res = useAsyncResource(load);
  useInterval(res.reload, REFRESH_MS);
  return res;
}

const isDay = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v);

/**
 * Accountability dashboard (design D, controls 3.6): every tile the tenant's OVERSIGHT policy shows,
 * each figure opening the list behind it.
 */
export function AccountabilityPage() {
  const { hasPermission } = useSession();
  const timeZone = useDisplayTimeZone();
  const [params, setParams] = useSearchParams();
  const [from, setFrom] = useState(() => params.get('date_from') ?? '');
  const [to, setTo] = useState(() => params.get('date_to') ?? '');
  const backwards = isDay(from) && isDay(to) && from > to;
  const res = useSummary(isDay(from) && !backwards ? from : '', isDay(to) && !backwards ? to : '');
  const data = res.data;
  const syncPeriod = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (isDay(value)) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };
  return (
    <>
      <PageHeader
        title="Accountability"
        subtitle={
          data === null
            ? 'Hours, engine hours, cash and approvals at a glance'
            : `As of ${formatInstantIn(data.as_of, timeZone)}`
        }
        actions={
          <Button
            startIcon={<Refresh />}
            variant="outlined"
            onClick={res.reload}
            loading={res.loading && data !== null}
          >
            Refresh
          </Button>
        }
      />
      <Box className="mb-4">
        <DashboardPeriod
          from={from}
          to={to}
          onFrom={(v) => {
            setFrom(v);
            syncPeriod('date_from', v);
          }}
          onTo={(v) => {
            setTo(v);
            syncPeriod('date_to', v);
          }}
          onClear={() => {
            setFrom('');
            setTo('');
            setParams({}, { replace: true });
          }}
        />
        {backwards && (
          <Alert severity="error" className="mt-2">
            The start of the period is after its end.
          </Alert>
        )}
      </Box>
      <AsyncContent
        resource={res}
        errorTitle="Could not load the accountability summary"
        loadingLabel="Loading accountability summary"
      >
        {(d) => (
          <Box className="flex flex-col gap-6">
            <ManagementDashboard data={d} />
            <Box component="section" aria-label="Other controls" className="flex flex-col gap-3">
              <Typography variant="h6" component="h2">
                Other controls
              </Typography>
              <AccountabilityTiles data={d} can={(p) => hasPermission(p)} />
            </Box>
          </Box>
        )}
      </AsyncContent>
    </>
  );
}

/** The accountability tiles as the first section of the tenant dashboard (viewers with the permission). */
export function AccountabilityDashboardSection() {
  const { hasPermission } = useSession();
  const headingId = useId();
  const res = useSummary();
  return (
    <Box component="section" aria-labelledby={headingId} data-section="accountability">
      <Box className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <Typography id={headingId} variant="h6" component="h2">
          Accountability
        </Typography>
        <Link component={RouterLink} to={ROUTES.tenantAccountability} underline="hover">
          Open the accountability dashboard
        </Link>
      </Box>
      <AsyncContent
        resource={res}
        errorTitle="Could not load the accountability summary"
        loadingLabel="Loading accountability summary"
      >
        {(d) => <AccountabilityTiles data={d} can={(p) => hasPermission(p)} />}
      </AsyncContent>
    </Box>
  );
}
