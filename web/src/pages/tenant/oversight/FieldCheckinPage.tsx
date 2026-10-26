import MyLocationOutlined from '@mui/icons-material/MyLocationOutlined';
import { Alert, Box, Button, Link, Stack, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { withErrorCode } from '../../../api/lifecycle';
import { newUuid } from '../../../api/ids';
import type { CheckinSlotDto, SiteCheckinDto } from '../../../api/oversightTypes';
import { oversightService } from '../../../api/services/oversightService';
import { StaticTable } from '../../../components/data/StaticTable';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { DetailSection } from '../../../components/lifecycle/EntityDetailsLayout';
import { GPS_STATUS_LABELS } from '../../../components/meter/gps';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useCanMutate } from '../../../access/useCanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { fieldJobPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { attemptGpsFix } from '../../../utils/geolocation';
import { formatInstantIn } from '../../../utils/time';
import { nameOr } from '../shared/names';
import {
  CHECKIN_ERROR_HINTS,
  distanceText,
  SLOT_STATUS_LABELS,
  SLOT_STATUS_TONES,
} from './oversightDisplay';

const jobLink = (id: string | null | undefined, number: string | null | undefined) =>
  id == null ? (
    '—'
  ) : (
    <Link component={RouterLink} to={fieldJobPath(id)}>
      {nameOr(number, id)}
    </Link>
  );

/**
 * The supervisor's own site check-ins (DEC-031 M3) from a browser: the company's schedule
 * (made / missed / due / upcoming) and a GPS check-in now. The site and job are taken from the
 * job the person is running; the browser position is never invented when there is no fix.
 */
export function FieldCheckinPage() {
  const notify = useNotify();
  const canRecord = useCanMutate(PERMISSIONS.tenantSiteCheckinRecord);
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<SiteCheckinDto | null>(null);
  const load = useCallback((signal: AbortSignal) => oversightService.mine({}, signal), []);
  const res = useAsyncResource(load);
  const timeZone = res.data?.timezone ?? 'UTC';
  const checkIn = async () => {
    setBusy(true);
    try {
      const gps = await attemptGpsFix();
      const saved = await oversightService.record({
        client_id: newUuid(),
        captured_at: new Date().toISOString(),
        gps,
      });
      setLast(saved);
      if (saved.gps_status === 'FIX') notify.success('Checked in.');
      else
        notify.warning(
          `Checked in without a position (${GPS_STATUS_LABELS[saved.gps_status]}). Allow location access to record where you are.`,
        );
      res.reload();
    } catch (err) {
      notify.error(withErrorCode(err, CHECKIN_ERROR_HINTS));
    } finally {
      setBusy(false);
    }
  };
  const slotColumns: DataColumn<CheckinSlotDto>[] = [
    { id: 'at', header: 'Time', render: (s) => formatInstantIn(s.scheduled_at, timeZone) },
    {
      id: 'window',
      header: 'Window',
      render: (s) => `± ${String(s.window_minutes)} min`,
    },
    {
      id: 'status',
      header: 'Status',
      render: (s) => (
        <StatusChip
          status={s.status}
          tones={SLOT_STATUS_TONES}
          label={SLOT_STATUS_LABELS[s.status]}
        />
      ),
    },
    { id: 'job', header: 'Job', render: (s) => jobLink(s.job_id, s.job_number) },
  ];
  const checkinColumns: DataColumn<SiteCheckinDto>[] = [
    { id: 'at', header: 'When', render: (c) => formatInstantIn(c.captured_at, timeZone) },
    { id: 'site', header: 'Site', render: (c) => nameOr(c.job_site_name, c.job_site_id) },
    { id: 'job', header: 'Job', render: (c) => jobLink(c.job_id, c.job_number) },
    { id: 'gps', header: 'GPS', render: (c) => GPS_STATUS_LABELS[c.gps_status] },
    { id: 'distance', header: 'Distance', render: distanceText },
  ];
  return (
    <>
      <PageHeader
        title="Site check-in"
        subtitle="Check in at your site at the company's set times while you run a job"
        actions={
          canRecord ? (
            <Button
              variant="contained"
              startIcon={<MyLocationOutlined />}
              disabled={busy}
              onClick={() => {
                void checkIn();
              }}
            >
              {busy ? 'Getting your position…' : 'Check in now'}
            </Button>
          ) : undefined
        }
      />
      <AsyncContent resource={res} loadingLabel="Loading your check-ins">
        {(d) => {
          const due = d.slots.filter((s) => s.status === 'DUE');
          return (
            <Stack spacing={2}>
              {!d.required && (
                <Alert severity="info">
                  Check-ins are not required at the moment. You can still check in; your schedule
                  below shows any earlier times.
                </Alert>
              )}
              {due.length > 0 && (
                <Alert severity="warning">
                  A check-in is due now (window ± {d.window_minutes} min). Use “Check in now” at the
                  site.
                </Alert>
              )}
              {last !== null && (
                <Alert severity={last.within_distance === false ? 'warning' : 'success'}>
                  Checked in at {formatInstantIn(last.captured_at, timeZone)}
                  {last.job_site_id !== null &&
                    ` · ${nameOr(last.job_site_name, last.job_site_id)}`}{' '}
                  · {distanceText(last)}
                </Alert>
              )}
              <DetailSection title="Company settings">
                <KeyValueGrid
                  columns={4}
                  items={[
                    { label: 'Required', value: d.required ? 'Yes' : 'No' },
                    {
                      label: `Times (${d.timezone})`,
                      value: d.times.length === 0 ? 'None set' : d.times.join(', '),
                    },
                    { label: 'Window', value: `± ${String(d.window_minutes)} min` },
                    {
                      label: 'Distance from the site',
                      value:
                        d.max_distance_m === null
                          ? 'Distance shown only'
                          : `Up to ${String(d.max_distance_m)} m`,
                    },
                  ]}
                />
                <Typography variant="caption" color="text.secondary">
                  Your position is recorded only when you check in, and you see every check-in here.
                </Typography>
              </DetailSection>
              <DetailSection title="Schedule">
                {d.slots.length === 0 ? (
                  <Typography color="text.secondary">
                    No check-ins scheduled for you in this period.
                  </Typography>
                ) : (
                  <StaticTable
                    columns={slotColumns}
                    rows={d.slots}
                    getRowId={(s) => s.scheduled_at}
                    ariaLabel="Check-in schedule"
                    isRowMuted={(s) => s.status === 'UPCOMING'}
                  />
                )}
              </DetailSection>
              <DetailSection title="My check-ins">
                {d.checkins.length === 0 ? (
                  <Typography color="text.secondary">No check-ins in this period.</Typography>
                ) : (
                  <StaticTable
                    columns={checkinColumns}
                    rows={d.checkins}
                    getRowId={(c) => c.id}
                    ariaLabel="My check-ins"
                  />
                )}
              </DetailSection>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Showing {d.day_from} to {d.day_to}.
                </Typography>
              </Box>
            </Stack>
          );
        }}
      </AsyncContent>
    </>
  );
}
