import { Alert, Box, Button, Chip, Link, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useNavigate, useParams, useSearchParams } from 'react-router';
import type { SiteCheckinDto } from '../../../api/oversightTypes';
import { oversightService } from '../../../api/services/oversightService';
import type { JobSiteDto, StaffDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { StatusChip, type StatusTone } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { DetailSection } from '../../../components/lifecycle/EntityDetailsLayout';
import { GPS_STATUS_LABELS } from '../../../components/meter/gps';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { OVERSIGHT_ROUTES, siteCheckinPath } from '../../../navigation/oversightRoutes';
import { jobDetailPath, staffDetailPath } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import { StaffFilter } from '../shared/financePickers';
import { JobSiteFilter } from '../shared/lookupPickers';
import { nameOr } from '../shared/names';
import { RecordDetail } from '../shared/RecordDetail';
import { useRecordById } from '../shared/useRecordById';
import { CheckinLocationMap } from './CheckinLocationMap';
import { distanceText, isDay, periodError, SOURCE_LABELS } from './oversightDisplay';
import { PeriodFields } from './oversightParts';

const DISTANCE_TONES: Readonly<Record<string, StatusTone>> = {
  WITHIN: 'success',
  FARTHER: 'warning',
  NOT_JUDGED: 'default',
};

/** Distance verdict as a chip: within the set distance, farther, or not judged. */
export function DistanceChip({ c }: { c: SiteCheckinDto }) {
  if (c.within_distance === true)
    return <StatusChip status="WITHIN" tones={DISTANCE_TONES} label="Within the distance" />;
  if (c.within_distance === false)
    return <StatusChip status="FARTHER" tones={DISTANCE_TONES} label="Farther than set" />;
  return (
    <StatusChip
      status="NOT_JUDGED"
      tones={DISTANCE_TONES}
      label={c.distance_m === null ? 'No distance' : 'Distance only'}
    />
  );
}

const metres = (c: SiteCheckinDto) =>
  c.distance_m === null ? '—' : `${String(Math.round(c.distance_m))} m`;

/** Everyone's site check-ins (DEC-031 M3), newest first; read-only for the office. */
export function SiteCheckinsPage() {
  const timeZone = useDisplayTimeZone();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const urlStaff = params.get('staff_id') ?? undefined;
  const [staff, setStaff] = useState<StaffDto | null>(null);
  const [site, setSite] = useState<JobSiteDto | null>(null);
  const [from, setFrom] = useState(() => params.get('day_from') ?? '');
  const [to, setTo] = useState(() => params.get('day_to') ?? '');
  const fetchPage = useCallback<FetchPage<SiteCheckinDto>>(
    (query, signal) => oversightService.listCheckins(query, signal),
    [],
  );
  const problem = periodError(from, to);
  const columns: DataColumn<SiteCheckinDto>[] = [
    { id: 'at', header: 'When', render: (c) => formatInstantIn(c.captured_at, timeZone) },
    { id: 'who', header: 'Person', render: (c) => nameOr(c.staff_member_name, c.staff_member_id) },
    { id: 'site', header: 'Site', render: (c) => nameOr(c.job_site_name, c.job_site_id) },
    { id: 'job', header: 'Job', render: (c) => nameOr(c.job_number, c.job_id) },
    { id: 'gps', header: 'GPS', render: (c) => GPS_STATUS_LABELS[c.gps_status] },
    { id: 'distance', header: 'Distance', align: 'right', render: metres },
    { id: 'judged', header: 'Distance check', render: (c) => <DistanceChip c={c} /> },
    { id: 'source', header: 'From', render: (c) => SOURCE_LABELS[c.source] ?? c.source },
  ];
  return (
    <>
      <PageHeader
        title="Site check-ins"
        subtitle="GPS check-ins supervisors made at their sites at the company's set times"
      />
      <Stack spacing={2}>
        {problem !== null && <Alert severity="error">{problem}</Alert>}
        {urlStaff !== undefined && staff === null && (
          <Box>
            <Chip
              label="One person"
              onDelete={() => {
                const next = new URLSearchParams(params);
                next.delete('staff_id');
                setParams(next);
              }}
            />
          </Box>
        )}
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(c) => c.id}
          searchPlaceholder="Search person"
          filters={{
            staff_id: staff?.id ?? urlStaff,
            job_site_id: site?.id,
            day_from: isDay(from) && problem === null ? from : undefined,
            day_to: isDay(to) && problem === null ? to : undefined,
          }}
          emptyTitle="No site check-ins"
          emptyDescription="Check-ins appear here when the company asks supervisors to check in at their sites."
          isRowMuted={(c) => c.within_distance === false}
          onRowClick={(c) => {
            void navigate(siteCheckinPath(c.id));
          }}
          toolbar={
            <Box className="flex flex-wrap items-center gap-3">
              <PeriodFields from={from} to={to} onFrom={setFrom} onTo={setTo} />
              <Box sx={{ minWidth: 220 }}>
                <StaffFilter label="Person" value={staff} onChange={setStaff} />
              </Box>
              <Box sx={{ minWidth: 220 }}>
                <JobSiteFilter label="Site" value={site} onChange={setSite} />
              </Box>
            </Box>
          }
        />
      </Stack>
    </>
  );
}

const loadCheckin = (id: string, signal: AbortSignal) => oversightService.getCheckin(id, signal);

/** One site check-in: who, when, where (map pin), distance from the site and the job it belongs to. */
export function SiteCheckinDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(loadCheckin, id);
  return (
    <RecordDetail
      resource={res}
      what="site check-in"
      back={{ label: 'Site check-ins', to: OVERSIGHT_ROUTES.siteCheckins }}
      timeZone={timeZone}
      title={(c) => `Check-in · ${nameOr(c.staff_member_name, c.staff_member_id)}`}
      subtitle={(c) =>
        `${formatInstantIn(c.captured_at, timeZone)} · ${nameOr(c.job_site_name, c.job_site_id)}`
      }
      status={(c) => <DistanceChip c={c} />}
      links={(c) =>
        c.job_id === null ? null : (
          <Button component={RouterLink} to={jobDetailPath(c.job_id)} variant="outlined">
            Open the job
          </Button>
        )
      }
      items={(c) => [
        {
          label: 'Person',
          value: (
            <Link component={RouterLink} to={staffDetailPath(c.staff_member_id)}>
              {nameOr(c.staff_member_name, c.staff_member_id)}
            </Link>
          ),
        },
        { label: 'Recorded by', value: nameOr(c.recorded_by_name, c.recorded_by) },
        { label: 'Site', value: nameOr(c.job_site_name, c.job_site_id) },
        {
          label: 'Job',
          value:
            c.job_id === null ? (
              '—'
            ) : (
              <Link component={RouterLink} to={jobDetailPath(c.job_id)}>
                {nameOr(c.job_number, c.job_id)}
              </Link>
            ),
        },
        { label: 'GPS', value: GPS_STATUS_LABELS[c.gps_status] },
        {
          label: 'Coordinates',
          value:
            c.latitude === null || c.longitude === null
              ? 'None recorded (no coordinates are ever substituted)'
              : `${String(c.latitude)}, ${String(c.longitude)}`,
        },
        {
          label: 'Accuracy',
          value: c.accuracy_m === null ? '—' : `±${String(Math.round(c.accuracy_m))} m`,
        },
        { label: 'Distance from the site', value: distanceText(c) },
        { label: 'Recorded from', value: SOURCE_LABELS[c.source] ?? c.source },
      ]}
      history={(c) => [
        { key: 'captured', label: 'Checked in', at: c.captured_at },
        { key: 'received', label: 'Received by the server', at: c.received_at },
      ]}
    >
      {(c) =>
        c.latitude === null || c.longitude === null ? null : (
          <DetailSection title="Location">
            <CheckinLocationMap
              latitude={c.latitude}
              longitude={c.longitude}
              accuracyM={c.accuracy_m}
            />
          </DetailSection>
        )
      }
    </RecordDetail>
  );
}
