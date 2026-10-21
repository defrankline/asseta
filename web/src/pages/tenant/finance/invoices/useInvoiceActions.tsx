import { Alert, Box } from '@mui/material';
import { useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useCanMutate } from '../../../../access/useCanMutate';
import { hireInvoiceService } from '../../../../api/services/financeService';
import type { HireInvoiceDto } from '../../../../api/types';
import { LifecycleActionDialog } from '../../../../components/lifecycle/LifecycleActionDialog';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { hireInvoiceDetailPath, hireInvoicePrintPath } from '../../../../navigation/routes';
import { useNotify } from '../../../../notifications/useNotify';
import { FINANCE_ERROR_HINTS } from '../../shared/financeDisplay';
import { VoidExplanation } from './InvoiceViews';
import { invoiceTitle } from './invoiceData';
import { IssueInvoiceDialog } from './IssueInvoiceDialog';

type Open = { kind: 'issue' | 'void'; invoice: HireInvoiceDto } | null;

interface Options {
  onChanged: (invoice: HireInvoiceDto) => void;
  /** Hide View (already on the details page). */
  onDetails?: boolean;
}

/** Row / details-page commands for a hire invoice: view, issue, void (with reason), print. */
export function useInvoiceActions({ onChanged, onDetails = false }: Options) {
  const navigate = useNavigate();
  const notify = useNotify();
  const canWrite = useCanMutate(PERMISSIONS.tenantFinanceInvoice);
  const [open, setOpen] = useState<Open>(null);
  const close = () => {
    setOpen(null);
  };

  const actionsFor = (i: HireInvoiceDto): RowAction[] => [
    {
      key: 'view',
      label: 'View details',
      hidden: onDetails,
      onClick: () => {
        void navigate(hireInvoiceDetailPath(i.id));
      },
    },
    {
      key: 'issue',
      label: 'Issue invoice',
      hidden: !canWrite || i.status !== 'DRAFT',
      onClick: () => {
        setOpen({ kind: 'issue', invoice: i });
      },
    },
    {
      key: 'print',
      label: 'Print view',
      hidden: i.status === 'DRAFT',
      onClick: () => {
        void navigate(hireInvoicePrintPath(i.id));
      },
    },
    {
      key: 'void',
      label: i.status === 'DRAFT' ? 'Discard draft (void)' : 'Void (reverse)',
      destructive: true,
      hidden: !canWrite || i.status === 'VOIDED',
      onClick: () => {
        setOpen({ kind: 'void', invoice: i });
      },
    },
  ];

  let dialogs: ReactNode = null;
  if (open?.kind === 'issue') {
    dialogs = (
      <IssueInvoiceDialog
        invoice={open.invoice}
        onClose={close}
        onIssued={(inv) => {
          notify.success(`Invoice ${invoiceTitle(inv)} issued.`);
          onChanged(inv);
        }}
      />
    );
  } else if (open?.kind === 'void') {
    const inv = open.invoice;
    dialogs = (
      <LifecycleActionDialog<HireInvoiceDto>
        title={`Void ${invoiceTitle(inv)}`}
        description={
          <Box className="flex flex-col gap-2">
            <VoidExplanation invoice={inv} />
            <Alert severity="warning">This cannot be undone.</Alert>
          </Box>
        }
        confirmLabel="Void invoice"
        destructive
        reasonHelp="3–1000 characters; shown on the invoice and the statement reversal."
        errorHints={FINANCE_ERROR_HINTS}
        onConfirm={(reason, key) => hireInvoiceService.void(inv.id, { reason }, key)}
        onDone={(result) => {
          notify.success(`Invoice ${invoiceTitle(result)} voided.`);
          onChanged(result);
        }}
        onClose={close}
      />
    );
  }
  return { actionsFor, dialogs };
}
