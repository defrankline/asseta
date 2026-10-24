import { Alert, Box, Button, Paper, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import { cashService } from '../../../../api/services/cashService';
import type { CashCustodyBalanceDto, StaffDto } from '../../../../api/types';
import { ExportMenu } from '../../../../components/data/ExportMenu';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../../components/feedback/EmptyState';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { StaffFilter } from '../../shared/financePickers';
import { RecordPaymentDialog } from '../payments/RecordPaymentDialog';
import { FloatDialog, HandoverDialog } from './CashDialogs';
import { ENTITY } from '../../../../realtime/entities';
import { useLiveRefresh } from '../../../../realtime/hooks';

type Open = 'float' | 'collection' | 'handover' | null;

export function BalanceCard({ b, timeZone }: { b: CashCustodyBalanceDto; timeZone: string }) {
  return (
    <Paper
      variant="outlined"
      className="p-4"
      aria-label={`Custody in ${b.currency}`}
      component="section"
    >
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
        {b.currency}
      </Typography>
      <KeyValueGrid
        columns={3}
        items={[
          {
            label: 'Outstanding accountability',
            value: <MoneyText amount={b.outstanding} currency={b.currency} strong />,
          },
          {
            label: 'Claimed handovers (not yet verified)',
            value: <MoneyText amount={b.claimed_unverified_handovers} currency={b.currency} />,
          },
          {
            label: 'Expenses pending approval',
            value: <MoneyText amount={b.pending_spending} currency={b.currency} />,
          },
          {
            label: 'Sent, not yet acknowledged (still held)',
            value: <MoneyText amount={b.in_transit_out} currency={b.currency} />,
          },
          {
            label: 'Incoming, not yet acknowledged',
            value: <MoneyText amount={b.in_transit_in} currency={b.currency} />,
          },
          {
            label: 'Floats awaiting acknowledgement',
            value: <MoneyText amount={b.pending_floats} currency={b.currency} />,
          },
          {
            label: 'Approved to keep (retention)',
            value: <MoneyText amount={b.approved_retention} currency={b.currency} />,
          },
        ]}
      />
      <Typography variant="caption" color="text.secondary">
        As of {formatInstantIn(b.as_of, timeZone)}. Outstanding = floats + collections + transfers
        received − transfers sent − approved cash expenses − confirmed remittances ± approved
        adjustments − written off; claims and transfers in transit do not change it until confirmed.
      </Typography>
    </Paper>
  );
}

interface CustodyTabProps {
  timeZone: string;
  supervisor: StaffDto | null;
  onSupervisorChange: (s: StaffDto | null) => void;
}

/** Per-supervisor cash custody (one balance per currency) and the cash movements that change it. */
export function CustodyTab({ timeZone, supervisor, onSupervisorChange }: CustodyTabProps) {
  const notify = useNotify();
  const can = useMutationGuard();
  const [open, setOpen] = useState<Open>(null);
  const staffId = supervisor?.id ?? '';
  const load = useCallback(
    (signal: AbortSignal) => cashService.custody(staffId, signal),
    [staffId],
  );
  const res = useAsyncResource(load, [], staffId !== '');
  useLiveRefresh([ENTITY.cashHandover, ENTITY.customerPayment, ENTITY.expense], res.reload);
  const close = () => {
    setOpen(null);
  };
  const done = (msg: string) => {
    notify.success(msg);
    res.reload();
  };
  return (
    <Box className="flex flex-col gap-3">
      <Box className="flex flex-wrap items-center gap-3">
        <Box sx={{ minWidth: 260 }}>
          <StaffFilter
            label="Custodian"
            placeholder="Choose a custodian"
            value={supervisor}
            onChange={onSupervisorChange}
          />
        </Box>
        <Box className="flex-1" />
        <ExportMenu reports={[{ code: 'cash', filters: { staff_member_id: supervisor?.id } }]} />
        {can(PERMISSIONS.tenantFinanceCash) && (
          <Button
            variant="outlined"
            onClick={() => {
              setOpen('float');
            }}
          >
            Record float
          </Button>
        )}
        {can(PERMISSIONS.tenantCollectionRecord) && (
          <>
            <Button
              variant="outlined"
              onClick={() => {
                setOpen('collection');
              }}
            >
              Record collection
            </Button>
            <Button
              variant="outlined"
              onClick={() => {
                setOpen('handover');
              }}
            >
              Record remittance
            </Button>
          </>
        )}
      </Box>
      {supervisor === null ? (
        <EmptyState
          title="Choose a custodian"
          description="Custody is held per custodian (any staff member) and per currency."
        />
      ) : (
        <AsyncContent
          resource={res}
          isEmpty={(rows) => rows.length === 0}
          emptyTitle="No cash custody yet"
          errorTitle="Could not load cash custody"
        >
          {(rows) => (
            <Box className="flex flex-col gap-3">
              {rows.map((b) => (
                <BalanceCard key={b.currency} b={b} timeZone={timeZone} />
              ))}
              <Alert severity="info">
                Use the Reconciliation tab for the day-by-day breakdown of this custodian’s cash;
                every figure opens the transactions behind it.
              </Alert>
            </Box>
          )}
        </AsyncContent>
      )}
      {open === 'float' && (
        <FloatDialog
          {...(staffId !== '' ? { staffMemberId: staffId } : {})}
          timeZone={timeZone}
          onClose={close}
          onRecorded={() => {
            done('Float recorded.');
          }}
        />
      )}
      {open === 'collection' && (
        <RecordPaymentDialog
          mode="collection"
          {...(staffId !== '' ? { staffMemberId: staffId } : {})}
          timeZone={timeZone}
          onClose={close}
          onRecorded={() => {
            done('Cash collection recorded (CLAIMED until verified).');
          }}
        />
      )}
      {open === 'handover' && (
        <HandoverDialog
          {...(staffId !== '' ? { staffMemberId: staffId } : {})}
          timeZone={timeZone}
          onClose={close}
          onRecorded={() => {
            done('Handover recorded (CLAIMED until verified).');
          }}
        />
      )}
    </Box>
  );
}
