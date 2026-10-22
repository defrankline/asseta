import { Alert, Box, Paper, Stack, Tab, Tabs } from '@mui/material';
import { useSearchParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { NEUTRAL_SIGNAL_NOTICE } from '../../../components/intelligence/signalText';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useSession } from '../../../session/useSession';
import { CasesTab } from './CasesTab';
import { SignalsTab } from './SignalsTab';

type TabKey = 'cases' | 'signals';

/** Investigations (backend `tenant.cases` menu): cases for review and, with `tenant.signal.read`, raw signals. */
export function CasesPage() {
  const timeZone = useDisplayTimeZone();
  const { hasPermission } = useSession();
  const canSeeSignals = hasPermission(PERMISSIONS.tenantSignalRead);
  const [params, setParams] = useSearchParams();
  const tab: TabKey = canSeeSignals && params.get('tab') === 'signals' ? 'signals' : 'cases';
  return (
    <>
      <PageHeader
        title="Investigations"
        subtitle="Evidence from deterministic signals, grouped into cases for human review"
      />
      <Stack spacing={2}>
        <Alert severity="info">{NEUTRAL_SIGNAL_NOTICE}</Alert>
        <Paper variant="outlined">
          <Tabs
            value={tab}
            aria-label="Investigations"
            onChange={(_e, v: TabKey) => {
              setParams({ tab: v });
            }}
          >
            <Tab value="cases" label="Cases" />
            {canSeeSignals && <Tab value="signals" label="Signals" />}
          </Tabs>
          <Box className="p-3">
            {tab === 'signals' ? (
              <SignalsTab timeZone={timeZone} />
            ) : (
              <CasesTab timeZone={timeZone} />
            )}
          </Box>
        </Paper>
      </Stack>
    </>
  );
}
