import { Alert, Box, Link, Stack, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { MachineMapDto } from '../../../api/types';
import { AgeText } from '../../../components/display/AgeText';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { ConnectivityChip } from '../../../components/fleet/ConnectivityChip';
import { StatusDimensions } from '../../../components/fleet/StatusDimensions';
import { machineDetailPath, ROUTES } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import { humanize } from '../../../utils/text';

interface MachineStatusPanelProps {
  machine: MachineMapDto;
  now: number;
  timeZone: string;
  /** Show the name as a link to the machine detail page. */
  linkToDetail?: boolean;
}

function orDash(value: string | null): string {
  return value === null || value === '' ? '—' : value;
}

/** Status evidence for one machine: connectivity, four status dimensions, position and age. */
export function MachineStatusPanel({
  machine: m,
  now,
  timeZone,
  linkToDetail = false,
}: MachineStatusPanelProps) {
  const positioned = m.longitude !== null && m.latitude !== null;
  return (
    <Stack spacing={2} aria-label={`Status of ${m.asset_code}`} component="section">
      <Box className="flex flex-wrap items-center justify-between gap-2">
        <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 600 }}>
          {linkToDetail ? (
            <Link component={RouterLink} to={machineDetailPath(m.machine_id)}>
              {m.asset_code} · {m.name}
            </Link>
          ) : (
            `${m.asset_code} · ${m.name}`
          )}
        </Typography>
        <ConnectivityChip connectivity={m.connectivity} isLive={m.is_live} />
      </Box>
      {!positioned ? (
        <Alert severity="info">No position has been received for this machine.</Alert>
      ) : (
        !m.is_live && (
          <Alert severity="warning">
            Last known position — not live. Reported{' '}
            <AgeText at={m.position_time} now={now} timeZone={timeZone} />.
          </Alert>
        )
      )}
      <StatusDimensions
        reportedWorkStatus={m.reported_work_status}
        observedEngine={m.observed_engine}
        observedMotion={m.observed_motion}
        locationCompliance={m.location_compliance}
      />
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Position time', value: formatInstantIn(m.position_time, timeZone, true) },
          {
            label: 'Position age',
            value: <AgeText at={m.position_time} now={now} timeZone={timeZone} />,
          },
          {
            label: 'Accuracy',
            value:
              m.accuracy_m === null ? 'Not reported' : `± ${String(Math.round(m.accuracy_m))} m`,
          },
          { label: 'Source', value: orDash(m.position_source) },
          {
            label: 'Position quality',
            value: m.position_quality === null ? '—' : humanize(m.position_quality),
          },
          {
            label: 'Last message',
            value: <AgeText at={m.last_message_at} now={now} timeZone={timeZone} />,
          },
          {
            label: 'Tracker state',
            value: m.tracker_state === null ? 'No tracker' : humanize(m.tracker_state),
          },
          { label: 'Machine status', value: humanize(m.machine_status) },
          { label: 'Supervisor', value: orDash(m.supervisor) },
          { label: 'Operator', value: orDash(m.operator) },
          {
            label: 'Open alerts',
            value:
              m.open_alerts > 0 ? (
                <Link component={RouterLink} to={ROUTES.tenantAlerts}>
                  {m.open_alerts} open
                </Link>
              ) : (
                'None'
              ),
          },
          { label: 'Policy version', value: m.policy_version },
        ]}
      />
    </Stack>
  );
}
