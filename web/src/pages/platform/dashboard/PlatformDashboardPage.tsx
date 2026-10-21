import Refresh from '@mui/icons-material/Refresh';
import { Box, Button, Card, CardContent, Stack, Typography } from '@mui/material';
import { useCallback, type ReactNode } from 'react';
import { platformDashboardService } from '../../../api/services/platformDashboardService';
import type { CurrencyTotalsDto, PlatformDashboardDto } from '../../../api/types';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip, type StatusTone } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { formatDate } from '../../../utils/dates';
import { ACCESS_TONES, SUBSCRIPTION_TONES, TENANT_STATUS_TONES } from '../shared/billingDisplay';

function CountsCard({
  title,
  counts,
  tones,
}: {
  title: string;
  counts: Readonly<Record<string, number>>;
  tones: Readonly<Record<string, StatusTone>>;
}) {
  const entries = Object.entries(counts).sort(([a], [b]) => a.localeCompare(b));
  const total = entries.reduce((sum, [, n]) => sum + n, 0);
  return (
    <Card variant="outlined" component="section" aria-label={title}>
      <CardContent>
        <Typography variant="overline" color="text.secondary">
          {title}
        </Typography>
        <Typography variant="h4" component="p" sx={{ fontWeight: 700 }}>
          {total}
        </Typography>
        {entries.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            None
          </Typography>
        ) : (
          <Stack component="ul" spacing={0.75} sx={{ listStyle: 'none', p: 0, m: 0, mt: 1 }}>
            {entries.map(([status, n]) => (
              <Box component="li" key={status} className="flex items-center justify-between gap-2">
                <StatusChip status={status} tones={tones} />
                <span style={{ fontVariantNumeric: 'tabular-nums' }}>{n}</span>
              </Box>
            ))}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" component="div">
        {label}
      </Typography>
      <Typography variant="body1" component="div" sx={{ fontWeight: 600 }}>
        {children}
      </Typography>
    </Box>
  );
}

/** One card per currency; amounts in different currencies are never added together. */
function CurrencyCard({ totals: t }: { totals: CurrencyTotalsDto }) {
  return (
    <Card variant="outlined" component="section" aria-label={`${t.currency} totals`}>
      <CardContent>
        <Typography variant="h6" component="h3" sx={{ fontWeight: 700 }}>
          {t.currency}
        </Typography>
        <Box className="mt-2 grid grid-cols-2 gap-3">
          <Metric label="Contracted MRR">
            <MoneyText amount={t.contracted_mrr} currency={t.currency} />
          </Metric>
          <Metric label="Contracted ARR">
            <MoneyText amount={t.contracted_arr} currency={t.currency} />
          </Metric>
          <Metric label="Billable / enrolled assets">
            {t.billable_assets} / {t.enrolled_assets}
          </Metric>
          <Metric label="Open invoices">{t.open_invoices}</Metric>
          <Metric label="Outstanding balance">
            <MoneyText amount={t.outstanding_balance} currency={t.currency} />
          </Metric>
        </Box>
      </CardContent>
    </Card>
  );
}

export function DashboardContent({ data }: { data: PlatformDashboardDto }) {
  return (
    <Stack spacing={3}>
      <Box className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <CountsCard
          title="Tenants by status"
          counts={data.tenants_by_status}
          tones={TENANT_STATUS_TONES}
        />
        <CountsCard
          title="Tenants by access"
          counts={data.tenants_by_access}
          tones={ACCESS_TONES}
        />
        <CountsCard
          title="Subscriptions by status"
          counts={data.subscriptions_by_status}
          tones={SUBSCRIPTION_TONES}
        />
        <Card variant="outlined" component="section" aria-label="Churn events (30 days)">
          <CardContent>
            <Typography variant="overline" color="text.secondary">
              Churn events (30 days)
            </Typography>
            <Typography variant="h4" component="p" sx={{ fontWeight: 700 }}>
              {data.churn_events_30d}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Cancellations and expiries in the last 30 days
            </Typography>
          </CardContent>
        </Card>
      </Box>
      <Box>
        <Typography variant="h6" component="h2" sx={{ mb: 0.5 }}>
          Revenue by currency
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Totals are reported per currency and never converted or summed across currencies.
        </Typography>
        {data.by_currency.length === 0 ? (
          <EmptyState title="No contracted revenue yet" />
        ) : (
          <Box className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.by_currency.map((t) => (
              <CurrencyCard key={t.currency} totals={t} />
            ))}
          </Box>
        )}
      </Box>
    </Stack>
  );
}

/** Platform owner dashboard (GET /platform/dashboard). */
export function PlatformDashboardPage() {
  const load = useCallback((signal: AbortSignal) => platformDashboardService.get(signal), []);
  const resource = useAsyncResource(load);
  return (
    <>
      <PageHeader
        title="Platform dashboard"
        subtitle={
          resource.data !== null
            ? `As of ${formatDate(resource.data.as_of)}`
            : 'Tenants, subscriptions and revenue'
        }
        actions={
          <Button
            startIcon={<Refresh />}
            variant="outlined"
            onClick={resource.reload}
            loading={resource.loading}
          >
            Refresh
          </Button>
        }
      />
      <AsyncContent
        resource={resource}
        errorTitle="Could not load the dashboard"
        loadingLabel="Loading dashboard"
      >
        {(data) => <DashboardContent data={data} />}
      </AsyncContent>
    </>
  );
}
