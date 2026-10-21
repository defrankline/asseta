import Close from '@mui/icons-material/Close';
import { Box, Button, Divider, Drawer, IconButton, Stack, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { CanMutate } from '../../../access/CanMutate';
import { trackerService } from '../../../api/services/trackerService';
import type { TrackerDto } from '../../../api/types';
import { AgeText } from '../../../components/display/AgeText';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { CapabilityMatrix } from '../../../components/fleet/CapabilityMatrix';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNow } from '../../../hooks/useNow';
import { machineDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { CAPABILITY_LABELS, TRACKER_STATE_TONES } from '../shared/display';
import { AssignTrackerDialog } from './AssignTrackerDialog';
import { TrackerStateDialog, UnassignTrackerDialog } from './TrackerActionDialogs';
import { STATE_TRANSITIONS } from './trackerForms';

type Action = 'assign' | 'unassign' | 'state' | null;

interface TrackerDrawerProps {
  trackerId: string;
  onClose: () => void;
  /** Something changed (list should refresh). */
  onChanged: () => void;
  onViewEvents: (tracker: TrackerDto) => void;
}

function TrackerDetail({
  tracker,
  timeZone,
  now,
}: {
  tracker: TrackerDto;
  timeZone: string;
  now: number;
}) {
  const a = tracker.current_assignment ?? null;
  return (
    <Stack spacing={2}>
      <KeyValueGrid
        columns={2}
        items={[
          {
            label: 'State',
            value: <StatusChip status={tracker.provisioning_state} tones={TRACKER_STATE_TONES} />,
          },
          { label: 'Adapter', value: tracker.adapter },
          { label: 'External id', value: tracker.external_id },
          { label: 'Model id', value: tracker.tracker_model_id },
          { label: 'SIM ICCID', value: tracker.sim_iccid ?? '—' },
          { label: 'SIM MSISDN', value: tracker.sim_msisdn ?? '—' },
          { label: 'Carrier', value: tracker.carrier ?? '—' },
          {
            label: 'First report',
            value: <AgeText at={tracker.first_report_at} now={now} timeZone={timeZone} />,
          },
          {
            label: 'Last report',
            value: <AgeText at={tracker.last_report_at} now={now} timeZone={timeZone} />,
          },
        ]}
      />
      <Divider />
      <Typography variant="subtitle2" component="h3">
        Current assignment
      </Typography>
      {a === null ? (
        <Typography variant="body2" color="text.secondary">
          Unassigned
        </Typography>
      ) : (
        <KeyValueGrid
          columns={2}
          items={[
            {
              label: 'Machine',
              value: (
                <RouterLink to={machineDetailPath(a.machine_id)}>
                  {a.machine_id.slice(0, 8)}
                </RouterLink>
              ),
            },
            { label: 'Primary', value: a.is_primary ? 'Yes' : 'No' },
            { label: 'Since', value: formatInstantIn(a.effective_from, timeZone) },
            { label: 'Reason', value: a.reason ?? '—' },
          ]}
        />
      )}
      <Divider />
      <Typography variant="subtitle2" component="h3">
        Capabilities
      </Typography>
      <CapabilityMatrix
        capabilities={tracker.capabilities}
        labels={CAPABILITY_LABELS}
        timeZone={timeZone}
        now={now}
      />
    </Stack>
  );
}

/** Tracker detail side panel with capability matrix and lifecycle actions. */
export function TrackerDrawer({ trackerId, onClose, onChanged, onViewEvents }: TrackerDrawerProps) {
  const notify = useNotify();
  const tz = useDisplayTimeZone();
  const now = useNow();
  const [action, setAction] = useState<Action>(null);
  const load = useCallback(
    (signal: AbortSignal) => trackerService.get(trackerId, signal),
    [trackerId],
  );
  const tracker = useAsyncResource(load);
  const done = (message: string) => {
    notify.success(message);
    tracker.reload();
    onChanged();
  };
  const t = tracker.data;
  const close = () => {
    setAction(null);
  };

  return (
    <Drawer
      anchor="right"
      open
      onClose={onClose}
      slotProps={{ paper: { sx: { width: { xs: '100%', sm: 560 } } } }}
    >
      <Box className="flex items-center justify-between p-3">
        <Typography variant="h6" component="h2">
          {t !== null ? `Tracker ${t.label}` : 'Tracker'}
        </Typography>
        <IconButton aria-label="Close" onClick={onClose}>
          <Close />
        </IconButton>
      </Box>
      <Divider />
      <Box className="p-3">
        <AsyncContent resource={tracker} errorTitle="Could not load the tracker">
          {(data) => (
            <Stack spacing={2}>
              <Box className="flex flex-wrap gap-2">
                <CanMutate permission={PERMISSIONS.tenantTrackerWrite}>
                  {data.provisioning_state !== 'RETIRED' && (
                    <Button
                      variant="contained"
                      size="small"
                      onClick={() => {
                        setAction('assign');
                      }}
                    >
                      Assign / swap
                    </Button>
                  )}
                  {data.current_assignment != null && (
                    <Button
                      size="small"
                      onClick={() => {
                        setAction('unassign');
                      }}
                    >
                      Unassign
                    </Button>
                  )}
                  {STATE_TRANSITIONS[data.provisioning_state].length > 0 && (
                    <Button
                      size="small"
                      onClick={() => {
                        setAction('state');
                      }}
                    >
                      Change state
                    </Button>
                  )}
                </CanMutate>
                <Button
                  size="small"
                  onClick={() => {
                    onViewEvents(data);
                  }}
                >
                  View ingestion events
                </Button>
              </Box>
              <TrackerDetail tracker={data} timeZone={tz} now={now} />
            </Stack>
          )}
        </AsyncContent>
      </Box>
      {t !== null && action === 'assign' && (
        <AssignTrackerDialog
          tracker={t}
          timeZone={tz}
          onClose={close}
          onAssigned={(a) => {
            done(a.is_primary ? 'Tracker assigned as primary.' : 'Tracker assigned.');
          }}
        />
      )}
      {t !== null && action === 'unassign' && (
        <UnassignTrackerDialog
          tracker={t}
          timeZone={tz}
          onClose={close}
          onDone={() => {
            done('Tracker unassigned.');
          }}
        />
      )}
      {t !== null && action === 'state' && (
        <TrackerStateDialog
          tracker={t}
          onClose={close}
          onDone={(next) => {
            done(`Tracker state changed to ${next.provisioning_state}.`);
          }}
        />
      )}
    </Drawer>
  );
}
