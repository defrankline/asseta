import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
} from '@mui/material';
import { useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type { AlertDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { machineDetailPath } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import {
  ALERT_SEVERITY_TONES,
  ALERT_STATUS_TONES,
  ALERT_TYPE_OPTIONS,
  labelOf,
  SUPERSEDED_HELP,
} from '../shared/display';
import { AlertActionDialog, type AlertAction } from './AlertActionDialog';
import { EvidenceView } from './EvidenceView';

interface AlertDetailDialogProps {
  alert: AlertDto;
  machineLabel: string | null;
  timeZone: string;
  onClose: () => void;
  onChanged: (alert: AlertDto) => void;
}

/** Alert detail with evidence; acknowledge / resolve for alert managers. */
export function AlertDetailDialog({
  alert,
  machineLabel,
  timeZone,
  onClose,
  onChanged,
}: AlertDetailDialogProps) {
  const [action, setAction] = useState<AlertAction | null>(null);
  const t = (v: string | null) => formatInstantIn(v, timeZone, true);
  const canAck = alert.status === 'OPEN';
  const canResolve = alert.status === 'OPEN' || alert.status === 'ACKNOWLEDGED';
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md" aria-labelledby="alert-detail-title">
      <DialogTitle id="alert-detail-title">{alert.title}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          {alert.status === 'SUPERSEDED' && <Alert severity="info">{SUPERSEDED_HELP}</Alert>}
          <KeyValueGrid
            items={[
              { label: 'Type', value: labelOf(ALERT_TYPE_OPTIONS, alert.alert_type) },
              {
                label: 'Severity',
                value: <StatusChip status={alert.severity} tones={ALERT_SEVERITY_TONES} />,
              },
              {
                label: 'Status',
                value: <StatusChip status={alert.status} tones={ALERT_STATUS_TONES} />,
              },
              { label: 'Event time', value: t(alert.event_time) },
              { label: 'Raised', value: t(alert.created_at) },
              {
                label: 'Machine',
                value:
                  alert.machine_id === null ? (
                    '—'
                  ) : (
                    <RouterLink to={machineDetailPath(alert.machine_id)}>
                      {machineLabel ?? alert.machine_id}
                    </RouterLink>
                  ),
              },
              { label: 'Tracker', value: alert.tracker_id ?? '—' },
              { label: 'Policy version', value: alert.policy_version ?? '—' },
              { label: 'Acknowledged', value: t(alert.acknowledged_at) },
              { label: 'Resolved', value: t(alert.resolved_at) },
              { label: 'Resolution note', value: alert.resolution_note ?? '—' },
            ]}
          />
          <EvidenceView evidence={alert.evidence} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <CanMutate permission={PERMISSIONS.tenantAlertManage}>
          {canAck && (
            <Button
              onClick={() => {
                setAction('ACKNOWLEDGE');
              }}
            >
              Acknowledge
            </Button>
          )}
          {canResolve && (
            <Button
              variant="contained"
              onClick={() => {
                setAction('RESOLVE');
              }}
            >
              Resolve
            </Button>
          )}
        </CanMutate>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
      {action !== null && (
        <AlertActionDialog
          alert={alert}
          action={action}
          onClose={() => {
            setAction(null);
          }}
          onDone={onChanged}
        />
      )}
    </Dialog>
  );
}
