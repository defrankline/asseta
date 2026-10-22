import Add from '@mui/icons-material/Add';
import { Box, Button, Link, Stack, Typography } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { platformPaymentService } from '../../../api/services/platformPaymentService';
import type { PaymentDto, TenantDto } from '../../../api/types';
import { AsyncAutocomplete } from '../../../components/data/AsyncAutocomplete';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { platformInvoiceDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { useSession } from '../../../session/useSession';
import { formatMoney, isZeroDecimal } from '../../../utils/money';
import { PAYMENT_COLUMNS } from '../shared/paymentColumns';
import { searchTenants, tenantLabel } from '../shared/platformLookups';
import { AllocatePaymentDialog } from './AllocatePaymentDialog';
import { PaymentDecisionDialog } from './PaymentDecisionDialog';
import { RecordTenantPaymentDialog } from './RecordTenantPaymentDialog';

type Dialog =
  | { kind: 'decide'; payment: PaymentDto; verified: boolean }
  | { kind: 'allocate'; payment: PaymentDto & { unallocated: string } }
  | { kind: 'record' }
  | null;

const sameTenant = (a: TenantDto, b: TenantDto) => a.id === b.id;

function hasUnallocated(p: PaymentDto): p is PaymentDto & { unallocated: string } {
  return p.status === 'VERIFIED' && p.unallocated != null && !isZeroDecimal(p.unallocated);
}

/** Where the money went: allocations per invoice / line, and what is still unallocated. */
function Allocations({ p }: { p: PaymentDto }) {
  const active = p.allocations.filter((a) => a.released_at === null);
  return (
    <Box>
      {p.invoice_id === null ? (
        <Typography variant="body2">Tenant-level</Typography>
      ) : (
        <Link component={RouterLink} to={platformInvoiceDetailPath(p.invoice_id)} variant="body2">
          For an invoice
        </Link>
      )}
      {active.length > 0 && (
        <Typography variant="caption" color="text.secondary" component="div">
          {active.length} allocation{active.length === 1 ? '' : 's'}
          {active.some((a) => a.line_id !== null) ? ' (incl. specific lines)' : ''}
        </Typography>
      )}
      {p.unallocated != null && !isZeroDecimal(p.unallocated) && (
        <Typography variant="caption" color="warning.main" component="div">
          Unallocated {formatMoney(p.unallocated, p.currency)}
        </Typography>
      )}
    </Box>
  );
}

/**
 * Platform payments: tenant-level or per invoice, manual verify / reject, allocation of verified
 * money to invoice lines (server paging, tenant filter, live refresh).
 */
export function PaymentsPage() {
  const notify = useNotify();
  const { hasPermission, me } = useSession();
  const canManage = hasPermission(PERMISSIONS.platformPaymentManage);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [tenant, setTenant] = useState<TenantDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  useLiveRefresh([ENTITY.platformPayment, ENTITY.platformInvoice], reload);
  const filters = useMemo(() => ({ tenant_id: tenant?.id }), [tenant]);
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      platformPaymentService.list(
        {
          page: q.page,
          page_size: q.page_size,
          ...(q.filters.tenant_id !== undefined ? { tenant_id: q.filters.tenant_id } : {}),
        },
        signal,
      ),
    [],
  );
  const close = () => {
    setDialog(null);
  };

  const columns: DataColumn<PaymentDto>[] = [
    ...PAYMENT_COLUMNS,
    { id: 'applied', header: 'Applied to', render: (p) => <Allocations p={p} /> },
    {
      id: 'actions',
      header: 'Actions',
      align: 'right',
      render: (p) => {
        if (
          p.status === 'RECORDED' &&
          canManage &&
          p.recorded_by !== null &&
          p.recorded_by === me?.user_id
        ) {
          // Two-person rule: the API refuses SEGREGATION_OF_DUTIES; say so up front instead of offering the action.
          return (
            <Typography variant="caption" color="text.secondary">
              Recorded by you — another staff member must verify
            </Typography>
          );
        }
        if (p.status === 'RECORDED' && canManage) {
          return (
            <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end' }}>
              <Button
                size="small"
                onClick={() => {
                  setDialog({ kind: 'decide', payment: p, verified: true });
                }}
              >
                Verify
              </Button>
              <Button
                size="small"
                color="error"
                onClick={() => {
                  setDialog({ kind: 'decide', payment: p, verified: false });
                }}
              >
                Reject
              </Button>
            </Stack>
          );
        }
        if (hasUnallocated(p) && canManage) {
          return (
            <Button
              size="small"
              onClick={() => {
                setDialog({ kind: 'allocate', payment: p });
              }}
            >
              Allocate
            </Button>
          );
        }
        return p.decision_note ?? '—';
      },
    },
  ];

  return (
    <>
      <PageHeader
        title="Payments"
        subtitle="Payments received from tenants: verification and allocation to invoice lines"
        actions={
          <Can permission={PERMISSIONS.platformPaymentManage}>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setDialog({ kind: 'record' });
              }}
            >
              Record payment
            </Button>
          </Can>
        }
      />
      <ServerDataTable<PaymentDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(p) => p.id}
        filters={filters}
        searchable={false}
        emptyTitle="No payments recorded"
        reloadKey={reloadKey}
        toolbar={
          <Box sx={{ minWidth: 260 }}>
            <AsyncAutocomplete<TenantDto>
              label="Tenant"
              size="small"
              value={tenant}
              onChange={setTenant}
              fetchOptions={searchTenants}
              getOptionLabel={tenantLabel}
              isOptionEqualToValue={sameTenant}
            />
          </Box>
        }
      />
      {dialog?.kind === 'decide' && (
        <PaymentDecisionDialog
          payment={dialog.payment}
          verified={dialog.verified}
          onClose={close}
          onDecided={(p) => {
            notify.success(p.status === 'VERIFIED' ? 'Payment verified.' : 'Payment rejected.');
            reload();
          }}
        />
      )}
      {dialog?.kind === 'allocate' && (
        <AllocatePaymentDialog
          payment={dialog.payment}
          onClose={close}
          onAllocated={() => {
            notify.success('Payment allocated.');
            reload();
          }}
        />
      )}
      {dialog?.kind === 'record' && (
        <RecordTenantPaymentDialog
          onClose={close}
          onRecorded={() => {
            notify.success('Payment recorded; verify it to apply it.');
            reload();
          }}
        />
      )}
    </>
  );
}
