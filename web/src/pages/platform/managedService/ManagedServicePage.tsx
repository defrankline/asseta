import Add from '@mui/icons-material/Add';
import { Alert, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { mandateService } from '../../../api/services/mandateService';
import type { MandateDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { MANDATE_TONES } from '../../../components/mandate/mandateUi';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { mandateScopeLabel } from '../../../session/mandateDisplay';
import { useSession } from '../../../session/useSession';
import { formatDate } from '../../../utils/dates';
import { GrantMandateDialog } from './GrantMandateDialog';
import { MandateDetailDialog } from './MandateDetailDialog';

const columns: DataColumn<MandateDto>[] = [
  { id: 'reference', header: 'Reference', render: (m) => <strong>{m.reference}</strong> },
  { id: 'client', header: 'Client', render: (m) => m.tenant_name },
  { id: 'scope', header: 'Scope', render: (m) => mandateScopeLabel(m.scope) },
  { id: 'from', header: 'From', render: (m) => formatDate(m.starts_on) },
  {
    id: 'until',
    header: 'Until',
    render: (m) => (m.ends_on === null ? 'Until ended' : formatDate(m.ends_on)),
  },
  { id: 'consent', header: 'Consent reference', render: (m) => m.consent_reference },
  { id: 'granted', header: 'Granted by', render: (m) => m.granted_by },
  { id: 'staff', header: 'Staff', align: 'right', render: (m) => m.active_staff },
  {
    id: 'status',
    header: 'Status',
    render: (m) => <StatusChip status={m.status} tones={MANDATE_TONES} />,
  },
];

/** Platform view of managed-service mandates: grant on consent, staff, and end them. */
export function ManagedServicePage() {
  const notify = useNotify();
  const { reload: reloadSession } = useSession();
  const [granting, setGranting] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const load = useCallback((signal: AbortSignal) => mandateService.list(signal), []);
  const mandates = useAsyncResource(load);
  /**
   * Granting, staffing or ending a mandate changes which clients platform staff may enter: refresh
   * the session (/me, in the background) so the header switcher lists them without a page reload.
   */
  const changed = () => {
    mandates.reload();
    reloadSession();
  };

  return (
    <>
      <PageHeader
        title="Managed service"
        subtitle="Consented, audited access for Asseta staff to operate a client's account"
        actions={
          <Can permission={PERMISSIONS.platformMandateManage}>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setGranting(true);
              }}
            >
              Grant mandate
            </Button>
          </Can>
        }
      />
      <Alert severity="info" className="mb-4">
        A mandate is granted on the client&apos;s written consent and takes effect immediately. The
        client&apos;s administrators see it and can revoke it at any time. Approvals still need two
        different people, so under a mandate two different staff members prepare and approve.
        Everything staff do is recorded against the mandate.
      </Alert>
      <AsyncContent
        resource={mandates}
        isEmpty={(rows) => rows.length === 0}
        emptyTitle="No mandates yet"
        emptyDescription="Grant a mandate once a client has consented in writing."
        loadingLabel="Loading mandates"
      >
        {(rows) => (
          <StaticTable
            columns={columns}
            rows={rows}
            getRowId={(m) => m.id}
            ariaLabel="Mandates"
            onRowClick={(m) => {
              setOpenId(m.id);
            }}
          />
        )}
      </AsyncContent>
      {granting && (
        <GrantMandateDialog
          onClose={() => {
            setGranting(false);
          }}
          onGranted={(m) => {
            notify.success(`Mandate ${m.reference} granted for ${m.tenant_name}.`);
            changed();
            setOpenId(m.id);
          }}
        />
      )}
      {openId !== null && (
        <MandateDetailDialog
          mandateId={openId}
          onClose={() => {
            setOpenId(null);
          }}
          onChanged={changed}
        />
      )}
    </>
  );
}
