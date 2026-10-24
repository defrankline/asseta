import Refresh from '@mui/icons-material/Refresh';
import { Box, Button, Link, Typography } from '@mui/material';
import { useCallback, useId } from 'react';
import { Link as RouterLink } from 'react-router';
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

const REFRESH_MS = 5 * 60_000;

function useSummary() {
  const load = useCallback((signal: AbortSignal) => accountabilityService.summary(signal), []);
  const res = useAsyncResource(load);
  useInterval(res.reload, REFRESH_MS);
  return res;
}

/**
 * Accountability dashboard (design D, controls 3.6): every tile the tenant's OVERSIGHT policy shows,
 * each figure opening the list behind it.
 */
export function AccountabilityPage() {
  const { hasPermission } = useSession();
  const timeZone = useDisplayTimeZone();
  const res = useSummary();
  const data = res.data;
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
      <AsyncContent
        resource={res}
        errorTitle="Could not load the accountability summary"
        loadingLabel="Loading accountability summary"
      >
        {(d) => <AccountabilityTiles data={d} can={(p) => hasPermission(p)} />}
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
