import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { subscriptionService } from '../../../api/services/subscriptionService';
import type { RateVersionDto, SubscriptionDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { MoneyText } from '../../../components/display/MoneyText';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { formatDate } from '../../../utils/dates';
import { formatPercent } from '../../../utils/money';
import { CADENCE_OPTIONS, optionLabel } from '../shared/billingDisplay';
import { NewRateVersionDialog } from './NewRateVersionDialog';

const columns: DataColumn<RateVersionDto>[] = [
  { id: 'version', header: 'Version', render: (r) => `v${String(r.version)}` },
  { id: 'from', header: 'Effective from', render: (r) => formatDate(r.effective_from) },
  { id: 'cadence', header: 'Cadence', render: (r) => optionLabel(CADENCE_OPTIONS, r.cadence) },
  {
    id: 'price',
    header: 'Unit price',
    align: 'right',
    render: (r) => <MoneyText amount={r.unit_price} currency={r.currency} />,
  },
  { id: 'min', header: 'Min. assets', align: 'right', render: (r) => r.minimum_billable_assets },
  {
    id: 'discount',
    header: 'Discount',
    align: 'right',
    render: (r) => formatPercent(r.discount_percent),
  },
  {
    id: 'tax',
    header: 'Tax',
    render: (r) => `${r.tax_name ?? 'Tax'} ${formatPercent(r.tax_rate_percent)}`,
  },
  { id: 'reason', header: 'Reason', render: (r) => r.reason },
];

export function RateVersionsTab({ subscription }: { subscription: SubscriptionDto }) {
  const notify = useNotify();
  const [creating, setCreating] = useState(false);
  const load = useCallback(
    (signal: AbortSignal) => subscriptionService.listRateVersions(subscription.id, signal),
    [subscription.id],
  );
  const rates = useAsyncResource(load);
  return (
    <Box>
      <Can permission={PERMISSIONS.platformPricingManage}>
        <Box className="mb-2 flex justify-end">
          <Button
            startIcon={<Add />}
            variant="outlined"
            onClick={() => {
              setCreating(true);
            }}
          >
            New rate version
          </Button>
        </Box>
      </Can>
      <AsyncContent resource={rates} isEmpty={(r) => r.length === 0} emptyTitle="No rate versions">
        {(rows) => (
          <StaticTable
            ariaLabel="Rate versions"
            columns={columns}
            rows={rows}
            getRowId={(r) => r.id}
          />
        )}
      </AsyncContent>
      {creating && (
        <NewRateVersionDialog
          subscriptionId={subscription.id}
          currentRate={subscription.current_rate}
          onClose={() => {
            setCreating(false);
          }}
          onCreated={(r) => {
            notify.success(`Rate version v${String(r.version)} created.`);
            rates.reload();
          }}
        />
      )}
    </Box>
  );
}
