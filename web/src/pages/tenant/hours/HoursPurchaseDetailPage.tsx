import { Button, Paper, Stack, Typography } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { hoursRequestService, hoursService } from '../../../api/services/hoursService';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { EntityDetailsLayout } from '../../../components/lifecycle/EntityDetailsLayout';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { HOURS_ROUTES, hoursLedgerPath } from '../../../navigation/hoursRoutes';
import { useNotify } from '../../../notifications/useNotify';
import { isZeroDecimal } from '../../../utils/money';
import { formatInstantIn } from '../../../utils/time';
import { shortId } from '../shared/financeDisplay';
import { PersonName } from '../shared/PersonName';
import { machineText, nameOr } from '../shared/names';
import { HoursOffNotice, ReasonDialog } from './HoursDialogs';
import { hoursText, PURCHASE_STATUS_LABELS, PURCHASE_STATUS_TONES } from './hoursDisplay';
import { PaymentEvidenceDialog } from './PaymentEvidenceDialog';
import {
  ActivateOnCreditDialog,
  AllocatePaymentDialog,
  RequestTransferDialog,
} from './PurchaseActionDialogs';
import { useCancellationRequests, useTransferRequests } from './useHoursRequests';
import { useHoursPolicy } from './useHoursPolicy';

type Open = 'allocate' | 'credit' | 'transfer' | 'cancel' | null;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Paper variant="outlined" className="p-4">
      <Stack spacing={2}>
        <Typography variant="h6" component="h2">
          {title}
        </Typography>
        {children}
      </Stack>
    </Paper>
  );
}

/** Transfers and cancellations of one purchase (decide / withdraw in place). */
function PurchaseRequests({ purchaseId, reloadKey }: { purchaseId: string; reloadKey: number }) {
  const load = useCallback(
    async (signal: AbortSignal) => {
      const query = { page: 1, page_size: 100, filters: { purchase_id: purchaseId } };
      const [transfers, cancellations] = await Promise.all([
        hoursRequestService.listTransfers(query, signal),
        hoursRequestService.listCancellations(query, signal),
      ]);
      return { transfers: transfers.items, cancellations: cancellations.items };
    },
    [purchaseId],
  );
  const res = useAsyncResource(load, [reloadKey]);
  const transfers = useTransferRequests(res.reload);
  const cancellations = useCancellationRequests(res.reload);
  return (
    <>
      <Section title="Transfers between machines">
        <AsyncContent
          resource={res}
          isEmpty={(d) => d.transfers.length === 0}
          emptyTitle="No transfers requested"
          errorTitle="Could not load transfers"
        >
          {(d) => (
            <StaticTable
              ariaLabel="Transfers"
              columns={transfers.columns}
              rows={d.transfers}
              getRowId={(t) => t.id}
            />
          )}
        </AsyncContent>
      </Section>
      <Section title="Cancellation requests">
        <AsyncContent
          resource={res}
          isEmpty={(d) => d.cancellations.length === 0}
          emptyTitle="No cancellation requested"
          errorTitle="Could not load cancellations"
        >
          {(d) => (
            <StaticTable
              ariaLabel="Cancellations"
              columns={cancellations.columns}
              rows={d.cancellations}
              getRowId={(c) => c.id}
            />
          )}
        </AsyncContent>
      </Section>
      {transfers.dialogs}
      {cancellations.dialogs}
    </>
  );
}

/** One hours purchase: price snapshot, hours totals per machine, payments + evidence, requests. */
export function HoursPurchaseDetailPage() {
  const { purchaseId = '' } = useParams();
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const hours = useHoursPolicy();
  const canPurchase = useCanMutate(PERMISSIONS.tenantHoursPurchase);
  const canCredit = useCanMutate(PERMISSIONS.tenantHoursCreditActivate);
  const canTransfer = useCanMutate(PERMISSIONS.tenantHoursTransfer);
  const canCancel = useCanMutate(PERMISSIONS.tenantHoursCancel);
  const [open, setOpen] = useState<Open>(null);
  const [evidenceFor, setEvidenceFor] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const load = useCallback(
    (signal: AbortSignal) => hoursService.getPurchase(purchaseId, signal),
    [purchaseId],
  );
  const res = useAsyncResource(load, [reloadKey]);
  const p = res.data;
  const changed = () => {
    setReloadKey((k) => k + 1);
  };
  const close = () => {
    setOpen(null);
  };
  const live = p !== null && p.status !== 'CANCELLED' && hours.on;
  const creditOn =
    hours.policy === null ||
    (hours.policy.creditAllowed && hours.policy.activationBasis.includes('CREDIT'));
  const actions: RowAction[] =
    p === null
      ? []
      : [
          {
            key: 'allocate',
            label: 'Allocate payment',
            hidden: !canPurchase || !live || isZeroDecimal(p.totals.amount_outstanding),
            onClick: () => {
              setOpen('allocate');
            },
          },
          {
            key: 'credit',
            label: 'Activate on credit',
            hidden: !canCredit || !live || !creditOn || isZeroDecimal(p.totals.awaiting_activation),
            onClick: () => {
              setOpen('credit');
            },
          },
          {
            key: 'transfer',
            label: 'Request transfer',
            hidden: !canTransfer || !live || isZeroDecimal(p.totals.remaining),
            onClick: () => {
              setOpen('transfer');
            },
          },
          {
            key: 'cancel',
            label: 'Request cancellation',
            destructive: true,
            hidden: !canCancel || !live,
            onClick: () => {
              setOpen('cancel');
            },
          },
        ];
  const updated = (message: string) => {
    notify.success(message);
    changed();
  };
  return (
    <EntityDetailsLayout
      title={p === null ? 'Hours purchase' : p.purchase_number}
      subtitle="Prepaid customer hours"
      back={{ label: 'All hours purchases', to: HOURS_ROUTES.purchases }}
      {...(p !== null
        ? {
            status: (
              <StatusChip
                status={p.status}
                tones={PURCHASE_STATUS_TONES}
                label={PURCHASE_STATUS_LABELS[p.status]}
              />
            ),
            actions: <ActionButtons actions={actions} primaryKey="allocate" />,
          }
        : {})}
      inactive={
        p?.status === 'CANCELLED'
          ? {
              title: 'This purchase is cancelled.',
              since: p.cancelled_at === null ? null : formatInstantIn(p.cancelled_at, timeZone),
            }
          : null
      }
    >
      <HoursOffNotice off={hours.status === 'known' && !hours.on} />
      <AsyncContent resource={res} errorTitle="Could not load the hours purchase">
        {(d) => (
          <Stack spacing={3}>
            <Section title="Purchase">
              <KeyValueGrid
                columns={3}
                items={[
                  {
                    label: 'Customer',
                    value: `${nameOr(d.customer_name, d.customer_id)}${d.customer_kind === 'WALK_IN' ? ' (walk-in)' : ''}`,
                  },
                  {
                    label: 'Machine',
                    value: machineText(d.machine_code, d.machine_name, d.machine_id),
                  },
                  ...(d.job_site_id == null
                    ? []
                    : [{ label: 'Site', value: nameOr(d.job_site_name, d.job_site_id) }]),
                  { label: 'Hours bought', value: hoursText(d.hours) },
                  {
                    label: 'Rate card rate',
                    value: <MoneyText amount={d.hourly_rate} currency={d.currency} />,
                  },
                  { label: 'Approved discount', value: `${d.discount_percent} %` },
                  {
                    label: 'Effective rate',
                    value: <MoneyText amount={d.effective_rate} currency={d.currency} />,
                  },
                  {
                    label: 'Amount',
                    value: <MoneyText amount={d.amount} currency={d.currency} strong />,
                  },
                  {
                    label: 'Recorded by',
                    value: <PersonName userId={d.created_by} name={d.created_by_name} />,
                  },
                  { label: 'Recorded at', value: formatInstantIn(d.created_at, timeZone) },
                  { label: 'Source', value: d.source },
                  { label: 'Policy version', value: d.policy_version },
                  { label: 'Note', value: d.note ?? '—' },
                ]}
              />
            </Section>
            <Section title="Hours">
              <KeyValueGrid
                columns={4}
                items={[
                  { label: 'Purchased', value: hoursText(d.totals.purchased) },
                  { label: 'Activated', value: hoursText(d.totals.activated) },
                  {
                    label: 'From verified payments',
                    value: hoursText(d.totals.activated_from_payments),
                  },
                  { label: 'On credit', value: hoursText(d.totals.activated_on_credit) },
                  { label: 'Awaiting activation', value: hoursText(d.totals.awaiting_activation) },
                  { label: 'Used on jobs', value: hoursText(d.totals.consumed) },
                  { label: 'Transferred', value: hoursText(d.totals.transferred) },
                  { label: 'Expired', value: hoursText(d.totals.expired) },
                  { label: 'Reversed', value: hoursText(d.totals.reversed) },
                  { label: 'Remaining', value: <strong>{hoursText(d.totals.remaining)}</strong> },
                ]}
              />
              <StaticTable
                ariaLabel="Hours per machine"
                rows={d.machines}
                getRowId={(m) => m.machine_id}
                columns={[
                  {
                    id: 'machine',
                    header: 'Machine',
                    render: (m) => machineText(m.machine_code, m.machine_name, m.machine_id),
                  },
                  {
                    id: 'act',
                    header: 'Activated',
                    align: 'right',
                    render: (m) => hoursText(m.activated),
                  },
                  {
                    id: 'in',
                    header: 'In',
                    align: 'right',
                    render: (m) => hoursText(m.transferred_in),
                  },
                  {
                    id: 'out',
                    header: 'Out',
                    align: 'right',
                    render: (m) => hoursText(m.transferred_out),
                  },
                  {
                    id: 'used',
                    header: 'Used',
                    align: 'right',
                    render: (m) => hoursText(m.consumed),
                  },
                  {
                    id: 'rem',
                    header: 'Remaining',
                    align: 'right',
                    render: (m) => hoursText(m.remaining),
                  },
                ]}
              />
              <Button
                component={RouterLink}
                to={hoursLedgerPath({ purchase_id: d.id })}
                variant="outlined"
                sx={{ alignSelf: 'flex-start' }}
              >
                Open the hours ledger
              </Button>
            </Section>
            <Section title="Payments">
              <KeyValueGrid
                columns={3}
                items={[
                  {
                    label: 'Verified',
                    value: <MoneyText amount={d.totals.amount_verified} currency={d.currency} />,
                  },
                  {
                    label: 'Claimed, not yet verified',
                    value: (
                      <MoneyText
                        amount={d.totals.amount_claimed_unverified}
                        currency={d.currency}
                      />
                    ),
                  },
                  {
                    label: 'Outstanding',
                    value: <MoneyText amount={d.totals.amount_outstanding} currency={d.currency} />,
                  },
                ]}
              />
              <StaticTable
                ariaLabel="Payment allocations"
                rows={d.allocations}
                getRowId={(a) => a.id}
                isRowMuted={(a) => a.released_at !== null}
                columns={[
                  { id: 'pay', header: 'Payment', render: (a) => shortId(a.payment_id) },
                  {
                    id: 'amt',
                    header: 'Amount',
                    align: 'right',
                    render: (a) => <MoneyText amount={a.amount} currency={d.currency} />,
                  },
                  { id: 'st', header: 'Payment status', render: (a) => a.payment_status ?? '—' },
                  {
                    id: 'rel',
                    header: 'Link',
                    render: (a) =>
                      a.released_at === null ? 'Active' : (a.release_reason ?? 'Released'),
                  },
                  {
                    id: 'ev',
                    header: '',
                    align: 'right',
                    render: (a) => (
                      <Button
                        size="small"
                        onClick={() => {
                          setEvidenceFor(a.payment_id);
                        }}
                      >
                        Evidence
                      </Button>
                    ),
                  },
                ]}
              />
            </Section>
            <PurchaseRequests purchaseId={d.id} reloadKey={reloadKey} />
          </Stack>
        )}
      </AsyncContent>
      {p !== null && open === 'allocate' && (
        <AllocatePaymentDialog
          purchase={p}
          onClose={close}
          onDone={() => {
            updated('Payment allocated; hours activate when it is verified.');
          }}
        />
      )}
      {p !== null && open === 'credit' && (
        <ActivateOnCreditDialog
          purchase={p}
          onClose={close}
          onDone={() => {
            updated('Hours activated on credit.');
          }}
        />
      )}
      {p !== null && open === 'transfer' && (
        <RequestTransferDialog
          purchase={p}
          reasonCodeRequired={hours.policy?.reasonCodeRequired ?? false}
          onClose={close}
          onDone={() => {
            notify.success('Transfer requested; someone else decides it.');
            changed();
          }}
        />
      )}
      {p !== null && open === 'cancel' && (
        <ReasonDialog
          title={`Request cancellation of ${p.purchase_number}`}
          submitLabel="Request cancellation"
          reasonKind="CANCELLATION"
          reasonCodeRequired={hours.policy?.reasonCodeRequired ?? false}
          summary={
            <Typography variant="body2">
              Only hours not yet used can be cancelled; someone else decides the request.
            </Typography>
          }
          onSubmit={(body, key) => hoursService.requestCancellation(p.id, body, key)}
          onDone={() => {
            notify.success('Cancellation requested.');
            changed();
          }}
          onClose={close}
        />
      )}
      {evidenceFor !== null && (
        <PaymentEvidenceDialog
          paymentId={evidenceFor}
          canAttach={canPurchase}
          onClose={() => {
            setEvidenceFor(null);
          }}
        />
      )}
    </EntityDetailsLayout>
  );
}
