import { Button, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { platformPaymentService } from '../../../api/services/platformPaymentService';
import type { PaymentDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useNotify } from '../../../notifications/useNotify';
import { PAYMENT_COLUMNS } from '../shared/paymentColumns';
import { PaymentDecisionDialog } from './PaymentDecisionDialog';

interface Decision {
  payment: PaymentDto;
  verified: boolean;
}

/** Platform payments with manual verify / reject (server paging). */
export function PaymentsPage() {
  const notify = useNotify();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      platformPaymentService.list({ page: q.page, page_size: q.page_size }, signal),
    [],
  );

  const columns: DataColumn<PaymentDto>[] = [
    ...PAYMENT_COLUMNS,
    {
      id: 'actions',
      header: 'Actions',
      align: 'right',
      render: (p) =>
        p.status === 'RECORDED' ? (
          <Can permission={PERMISSIONS.platformPaymentManage} fallback="—">
            <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end' }}>
              <Button
                size="small"
                onClick={() => {
                  setDecision({ payment: p, verified: true });
                }}
              >
                Verify
              </Button>
              <Button
                size="small"
                color="error"
                onClick={() => {
                  setDecision({ payment: p, verified: false });
                }}
              >
                Reject
              </Button>
            </Stack>
          </Can>
        ) : (
          (p.decision_note ?? '—')
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Payments"
        subtitle="Manually recorded subscription payments awaiting or after verification"
      />
      <ServerDataTable<PaymentDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(p) => p.id}
        searchable={false}
        emptyTitle="No payments recorded"
        reloadKey={reloadKey}
      />
      {decision !== null && (
        <PaymentDecisionDialog
          payment={decision.payment}
          verified={decision.verified}
          onClose={() => {
            setDecision(null);
          }}
          onDecided={(p) => {
            notify.success(p.status === 'VERIFIED' ? 'Payment verified.' : 'Payment rejected.');
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
