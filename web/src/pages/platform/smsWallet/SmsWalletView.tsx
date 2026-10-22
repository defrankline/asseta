import { Alert, Box, Paper, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { usePlatformInvoicingService } from '../../../api/services/platformInvoicingService';
import type { SmsWalletEntryDto, SmsWalletEntryType } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip, type StatusTone } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { formatInstant } from '../../../utils/dates';
import { humanize } from '../../../utils/text';

const ENTRY_TONES: Readonly<Record<SmsWalletEntryType, StatusTone>> = {
  BUNDLE_CREDIT: 'success',
  BUNDLE_REVERSAL: 'warning',
  SMS_DEBIT: 'default',
  SMS_REFUND: 'info',
};

const ENTRY_LABELS: Readonly<Record<SmsWalletEntryType, string>> = {
  BUNDLE_CREDIT: 'Bundle credit',
  BUNDLE_REVERSAL: 'Bundle reversal',
  SMS_DEBIT: 'SMS sent',
  SMS_REFUND: 'SMS refund',
};

const count = (n: number) => n.toLocaleString('en-US');
const signed = (n: number) => (n > 0 ? `+${count(n)}` : count(n));

interface SmsWalletViewProps {
  /** Tenant id in the platform console; null for the active tenant (tenant console). */
  tenantId: string | null;
}

/** SMS credit balance and ledger (credits from paid SMS bundles, debits per SMS segment). */
export function SmsWalletView({ tenantId }: SmsWalletViewProps) {
  const service = usePlatformInvoicingService();
  const [reloadKey, setReloadKey] = useState(0);
  const loadWallet = useCallback(
    (signal: AbortSignal) => service.getSmsWallet(tenantId, signal),
    [service, tenantId],
  );
  const wallet = useAsyncResource(loadWallet);
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      service.listSmsWalletEntries(tenantId, { page: q.page, page_size: q.page_size }, signal),
    [service, tenantId],
  );
  const reload = useCallback(() => {
    wallet.reload();
    setReloadKey((k) => k + 1);
  }, [wallet]);
  // Bundle lines are fulfilled (or reversed) through platform invoice events.
  useLiveRefresh([ENTITY.platformInvoice], reload);

  const columns: DataColumn<SmsWalletEntryDto>[] = [
    { id: 'at', header: 'When', render: (e) => formatInstant(e.created_at) },
    {
      id: 'type',
      header: 'Entry',
      render: (e) => (
        <StatusChip status={e.entry_type} tones={ENTRY_TONES} label={ENTRY_LABELS[e.entry_type]} />
      ),
    },
    {
      id: 'reference',
      header: 'Reference',
      // Bundle notes carry the invoice number and line (e.g. `AST-2026-0000042 line 1: …`).
      render: (e) => e.note ?? humanize(e.reference_type),
    },
    { id: 'credits', header: 'Credits', align: 'right', render: (e) => signed(e.credits) },
    {
      id: 'balance',
      header: 'Balance after',
      align: 'right',
      render: (e) => count(e.balance_after),
    },
  ];

  return (
    <Box className="flex flex-col gap-4">
      <AsyncContent
        resource={wallet}
        loadingLabel="Loading SMS wallet"
        errorTitle="Could not load the SMS wallet"
      >
        {(w) => (
          <Box className="flex flex-col gap-2">
            <Box className="grid gap-3 sm:grid-cols-2">
              <Paper
                variant="outlined"
                className="p-4"
                aria-label="Available SMS credits"
                role="group"
              >
                <Typography variant="caption" color="text.secondary">
                  Available credits
                </Typography>
                <Typography variant="h4" component="p" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                  {count(w.balance)}
                </Typography>
              </Paper>
              <Paper variant="outlined" className="p-4">
                <Typography variant="caption" color="text.secondary">
                  Low-balance alert at
                </Typography>
                <Typography variant="h6" component="p">
                  {count(w.low_balance_threshold)} credits
                </Typography>
              </Paper>
            </Box>
            {w.balance <= w.low_balance_threshold && (
              <Alert severity={w.balance === 0 ? 'error' : 'warning'}>
                {w.balance === 0
                  ? 'The SMS wallet is empty: SMS notifications are refused until an SMS bundle is paid.'
                  : `Low SMS balance: ${count(w.balance)} credits left. SMS notifications stop when the wallet is empty.`}
              </Alert>
            )}
          </Box>
        )}
      </AsyncContent>
      <Typography variant="subtitle1" component="h2">
        Ledger
      </Typography>
      <ServerDataTable<SmsWalletEntryDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(e) => e.id}
        searchable={false}
        reloadKey={reloadKey}
        emptyTitle="No SMS wallet activity yet"
      />
    </Box>
  );
}
