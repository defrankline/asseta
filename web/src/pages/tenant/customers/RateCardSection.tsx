import Add from '@mui/icons-material/Add';
import { Alert, Box, Button, Paper, Stack, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { customerService } from '../../../api/services/customerService';
import { machineService } from '../../../api/services/machineService';
import type { CategoryDto, RateCardDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNow } from '../../../hooks/useNow';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { CategoryFilter } from '../shared/lookupPickers';
import { RateCardDialog, VERSIONING_NOTE } from './RateCardDialog';
import { groupRateCards, type VersionState } from './rateCardVersions';

type Row = { card: RateCardDto; state: VersionState };

const STATE_TONES = { IN_FORCE: 'success', SCHEDULED: 'info', SUPERSEDED: 'default' } as const;
const STATE_LABELS: Readonly<Record<VersionState, string>> = {
  IN_FORCE: 'In force',
  SCHEDULED: 'Scheduled',
  SUPERSEDED: 'Superseded',
};

/** Tenant rental rate cards per machine category with their full version history. */
export function RateCardSection({ timeZone }: { timeZone: string }) {
  const notify = useNotify();
  const { hasPermission } = useSession();
  const canWrite = useCanMutate(PERMISSIONS.tenantCustomerWrite);
  const canCategories = hasPermission(PERMISSIONS.tenantMachineRead);
  const now = useNow(60_000);
  const [creating, setCreating] = useState(false);
  const [category, setCategory] = useState<CategoryDto | null>(null);
  const categoryId = category?.id ?? '';
  const [reloadKey, setReloadKey] = useState(0);
  const loadCategories = useCallback(
    (signal: AbortSignal) => machineService.listCategories(signal),
    [],
  );
  const categories = useAsyncResource(loadCategories, [], canCategories);
  const loadCards = useCallback(
    (signal: AbortSignal) => customerService.listRateCards(categoryId || undefined, signal),
    [categoryId],
  );
  const cards = useAsyncResource(loadCards, [reloadKey]);
  const categoryName = (id: string) => categories.data?.find((c) => c.id === id)?.name ?? id;
  const columns: DataColumn<Row>[] = [
    {
      id: 'state',
      header: 'Version',
      render: (r) => (
        <StatusChip status={r.state} tones={STATE_TONES} label={STATE_LABELS[r.state]} />
      ),
    },
    {
      id: 'from',
      header: 'Effective from',
      render: (r) => formatInstantIn(r.card.effective_from, timeZone),
    },
    {
      id: 'rate',
      header: 'Hourly rate',
      align: 'right',
      render: (r) => <MoneyText amount={r.card.hourly_rate} currency={r.card.currency} />,
    },
    {
      id: 'min',
      header: 'Minimum hours',
      align: 'right',
      render: (r) => `${r.card.minimum_hours} h`,
    },
    { id: 'reason', header: 'Reason', render: (r) => r.card.reason },
  ];
  return (
    <Paper variant="outlined" className="p-4">
      <Stack spacing={2}>
        <Box className="flex flex-wrap items-center justify-between gap-2">
          <Typography variant="subtitle1" component="h2">
            Rental rate cards
          </Typography>
          <Box className="flex flex-wrap items-center gap-2">
            {canCategories && (
              <Box sx={{ minWidth: 220 }}>
                <CategoryFilter label="Machine category" value={category} onChange={setCategory} />
              </Box>
            )}
            {canWrite && (
              <Button
                variant="outlined"
                startIcon={<Add />}
                disabled={!canCategories}
                onClick={() => {
                  setCreating(true);
                }}
              >
                New rate-card version
              </Button>
            )}
          </Box>
        </Box>
        <Typography variant="body2" color="text.secondary">
          Your own hourly rental rates per machine category, used for jobs that do not carry a
          negotiated rate. {VERSIONING_NOTE}
        </Typography>
        {categories.error !== null && (
          <Alert severity="warning">
            Could not load machine categories: {categories.error.message}
          </Alert>
        )}
        <AsyncContent
          resource={cards}
          isEmpty={(d) => d.length === 0}
          emptyTitle="No rate cards yet"
          emptyDescription="Without a rate card, jobs need a negotiated hourly rate."
          errorTitle="Could not load rate cards"
        >
          {(d) => (
            <Stack spacing={2}>
              {groupRateCards(d, now).map((g) => (
                <Box key={g.categoryId}>
                  <Typography variant="subtitle2" component="h3">
                    {categoryName(g.categoryId)}
                  </Typography>
                  <StaticTable
                    ariaLabel={`Rate-card versions · ${categoryName(g.categoryId)}`}
                    columns={columns}
                    rows={g.versions}
                    getRowId={(r) => r.card.id}
                  />
                </Box>
              ))}
            </Stack>
          )}
        </AsyncContent>
      </Stack>
      {creating && (
        <RateCardDialog
          timeZone={timeZone}
          onClose={() => {
            setCreating(false);
          }}
          onCreated={(r) => {
            notify.success(`Rate-card version created for ${categoryName(r.machine_category_id)}.`);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </Paper>
  );
}
