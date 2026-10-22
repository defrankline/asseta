import { Alert, Box, Paper, Stack, Tab, Tabs, Typography } from '@mui/material';
import { useCallback } from 'react';
import { useSearchParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { insightsService } from '../../../api/services/insightsService';
import type { TenantInsightsDto } from '../../../api/types';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { ExportMenu } from '../../../components/data/ExportMenu';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useSession } from '../../../session/useSession';
import { CashFlowTab } from './CashFlowTab';
import { INSIGHTS_NOTICE } from './insightsDisplay';
import { FuelEfficiencyTab, UtilisationTab } from './MachineInsightTabs';
import { ManualOverridesTab } from './ManualOverridesTab';
import { MlStatusCard } from './MlStatusCard';
import { ObservationsTab } from './ObservationsTab';

type TabKey = 'fuel' | 'utilisation' | 'cash' | 'overrides' | 'observations';

const TAB_LABELS: Readonly<Record<TabKey, string>> = {
  fuel: 'Fuel efficiency',
  utilisation: 'Utilisation',
  cash: 'Cash flow',
  overrides: 'Manual overrides',
  observations: 'Model observations',
};

function MethodNotes({ method }: { method: readonly string[] }) {
  return (
    <Box component="section" aria-label="How these are computed" className="mt-4">
      <Typography variant="subtitle2" component="h3">
        How these are computed
      </Typography>
      <Box component="ul" className="m-0 pl-5">
        {method.map((m) => (
          <li key={m}>
            <Typography variant="body2" color="text.secondary">
              {m}
            </Typography>
          </li>
        ))}
      </Box>
    </Box>
  );
}

function BaselineTab({
  tab,
  data,
  timeZone,
}: {
  tab: 'fuel' | 'utilisation' | 'cash';
  data: TenantInsightsDto;
  timeZone: string;
}) {
  let body;
  if (tab === 'fuel') body = <FuelEfficiencyTab items={data.fuel_efficiency} timeZone={timeZone} />;
  else if (tab === 'utilisation')
    body = <UtilisationTab items={data.utilisation} timeZone={timeZone} />;
  else if (data.cash_flow === null)
    body = <Alert severity="info">Cash flow needs the finance reports permission.</Alert>;
  else body = <CashFlowTab flow={data.cash_flow} timeZone={timeZone} />;
  return (
    <>
      {body}
      <MethodNotes method={data.method} />
    </>
  );
}

/**
 * Insights (backend `tenant.insights` menu, `tenant.fleet.read`): the plain model status and baseline
 * insights — fuel efficiency, utilisation, cash flow (finance reports only), the OCR manual-override
 * audit (meter read) and surfaced model observations (case read). Tenants never see a model score.
 */
export function InsightsPage() {
  const timeZone = useDisplayTimeZone();
  const { hasPermission } = useSession();
  const visible: TabKey[] = [
    'fuel',
    'utilisation',
    ...(hasPermission(PERMISSIONS.tenantFinanceReport) ? (['cash'] as const) : []),
    ...(hasPermission(PERMISSIONS.tenantMeterRead) ? (['overrides'] as const) : []),
    ...(hasPermission(PERMISSIONS.tenantCaseRead) ? (['observations'] as const) : []),
  ];
  const [params, setParams] = useSearchParams();
  const requested = params.get('tab') as TabKey | null;
  const tab: TabKey = requested !== null && visible.includes(requested) ? requested : 'fuel';
  const load = useCallback((signal: AbortSignal) => insightsService.get(signal), []);
  const insights = useAsyncResource(load);
  return (
    <>
      <PageHeader
        title="Insights"
        subtitle="Each machine compared with its own history, plus model status and review aids"
        actions={<ExportMenu reports={[{ code: 'utilisation' }]} />}
      />
      <Stack spacing={2}>
        <Alert severity="info">{INSIGHTS_NOTICE}</Alert>
        {hasPermission(PERMISSIONS.tenantSignalRead) && <MlStatusCard timeZone={timeZone} />}
        <Paper variant="outlined">
          <Tabs
            value={tab}
            aria-label="Insights"
            variant="scrollable"
            onChange={(_e, v: TabKey) => {
              setParams({ tab: v });
            }}
          >
            {visible.map((k) => (
              <Tab key={k} value={k} label={TAB_LABELS[k]} />
            ))}
          </Tabs>
          <Box className="p-3">
            {tab === 'overrides' ? (
              <ManualOverridesTab timeZone={timeZone} />
            ) : tab === 'observations' ? (
              <ObservationsTab timeZone={timeZone} />
            ) : (
              <AsyncContent
                resource={insights}
                errorTitle="Could not load insights"
                loadingLabel="Loading insights"
              >
                {(data) => <BaselineTab tab={tab} data={data} timeZone={timeZone} />}
              </AsyncContent>
            )}
          </Box>
        </Paper>
      </Stack>
    </>
  );
}
