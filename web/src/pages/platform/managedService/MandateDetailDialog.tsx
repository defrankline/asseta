import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  Typography,
} from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { mandateService } from '../../../api/services/mandateService';
import type { MandateAssignmentDto, MandateDetailDto } from '../../../api/types';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { ConfirmDialog } from '../../../components/forms/ConfirmDialog';
import { CloseMandateForm } from '../../../components/mandate/CloseMandateForm';
import { MandateStaffTable } from '../../../components/mandate/MandateStaffTable';
import { MandateTerms } from '../../../components/mandate/MandateTerms';
import { isOpenMandate } from '../../../components/mandate/mandateUi';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { AssignStaffForm } from './AssignStaffForm';

interface MandateDetailDialogProps {
  mandateId: string;
  onClose: () => void;
  /** The mandate changed (staff, status); refresh the list. */
  onChanged: () => void;
}

function Section({ title }: { title: string }) {
  return (
    <Typography variant="subtitle2" component="h3" sx={{ fontWeight: 700 }}>
      {title}
    </Typography>
  );
}

/** Terms, staff assignments and the end-of-mandate control for one mandate. */
export function MandateDetailDialog({ mandateId, onClose, onChanged }: MandateDetailDialogProps) {
  const notify = useNotify();
  const { hasPermission } = useSession();
  const canManage = hasPermission(PERMISSIONS.platformMandateManage);
  const removeKey = useIdempotencyKey();
  const endKey = useIdempotencyKey();
  const load = useCallback(
    (signal: AbortSignal) => mandateService.get(mandateId, signal),
    [mandateId],
  );
  const resource = useAsyncResource(load, [mandateId]);
  /** Latest server copy after a mutation (each mutation returns the full detail). */
  const [updated, setUpdated] = useState<MandateDetailDto | null>(null);
  const [removing, setRemoving] = useState<MandateAssignmentDto | null>(null);
  const shown = { ...resource, data: updated ?? resource.data };

  const apply = (next: MandateDetailDto, message: string) => {
    setUpdated(next);
    notify.success(message);
    onChanged();
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md" aria-labelledby="mandate-detail-title">
      <DialogTitle id="mandate-detail-title">
        Mandate {shown.data?.reference ?? ''}
        {shown.data !== null && ` · ${shown.data.tenant_name}`}
      </DialogTitle>
      <DialogContent dividers>
        <AsyncContent resource={shown} loadingLabel="Loading mandate">
          {(m) => {
            const open = isOpenMandate(m.status);
            return (
              <Stack spacing={3}>
                <MandateTerms mandate={m} />
                <Divider />
                <Section title="Staff assignments" />
                <MandateStaffTable
                  assignments={m.assignments}
                  {...(canManage && open
                    ? {
                        renderAction: (a: MandateAssignmentDto) =>
                          a.is_active ? (
                            <Button
                              size="small"
                              color="error"
                              onClick={() => {
                                setRemoving(a);
                              }}
                            >
                              Remove
                            </Button>
                          ) : (
                            '—'
                          ),
                      }
                    : {})}
                />
                {canManage && open && (
                  <>
                    <Section title="Assign staff" />
                    <Alert severity="info">
                      Approvals still need two different people: assign at least two staff members
                      if they must prepare and approve for this client.
                    </Alert>
                    <AssignStaffForm
                      mandateId={m.id}
                      onAssigned={(next) => {
                        apply(next, 'Staff assigned.');
                      }}
                    />
                    <Divider />
                    <Section title="End mandate" />
                    <Typography variant="body2" color="text.secondary">
                      Ending withdraws every staff member's access to {m.tenant_name} immediately.
                    </Typography>
                    <CloseMandateForm
                      reasonLabel="Reason for ending"
                      submitLabel="End mandate"
                      onSubmit={async (reason) => {
                        const body = { version: m.version, reason };
                        apply(await mandateService.end(m.id, body, endKey(body)), 'Mandate ended.');
                      }}
                    />
                  </>
                )}
              </Stack>
            );
          }}
        </AsyncContent>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
      {removing !== null && (
        <ConfirmDialog
          open
          title="Remove staff access"
          message={`${removing.display_name} loses the ${removing.role_key} role at this client immediately.`}
          confirmLabel="Remove"
          destructive
          onClose={() => {
            setRemoving(null);
          }}
          onConfirm={async () => {
            const next = await mandateService.removeAssignment(
              mandateId,
              removing.id,
              removeKey(removing.id),
            );
            apply(next, 'Staff access removed.');
          }}
        />
      )}
    </Dialog>
  );
}
