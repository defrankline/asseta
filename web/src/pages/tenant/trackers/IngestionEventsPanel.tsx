import ExpandMore from '@mui/icons-material/ExpandMore';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Chip,
  MenuItem,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { useCallback } from 'react';
import { trackerService } from '../../../api/services/trackerService';
import type { IngestionEventDto, QuarantineReason, TrackerDto } from '../../../api/types';
import { AsyncAutocomplete } from '../../../components/data/AsyncAutocomplete';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import {
  INGESTION_STATUS_OPTIONS,
  INGESTION_STATUS_TONES,
  QUARANTINE_REASON_HELP,
} from '../shared/display';

export interface TrackerFilter {
  id: string;
  label: string;
}

interface IngestionEventsPanelProps {
  timeZone: string;
  status: string;
  onStatusChange: (status: string) => void;
  tracker: TrackerFilter | null;
  /** Omit to lock the panel to `tracker` (e.g. on the tracker details page). */
  onTrackerChange?: (tracker: TrackerFilter | null) => void;
}

function QuarantineReasonCell({ reason }: { reason: QuarantineReason | null }) {
  if (reason === null) return <>—</>;
  const help = QUARANTINE_REASON_HELP[reason];
  return (
    <Tooltip title={help}>
      <Box>
        <Typography variant="body2">{humanize(reason)}</Typography>
        <Typography variant="caption" color="text.secondary">
          {help}
        </Typography>
      </Box>
    </Tooltip>
  );
}

export function QuarantineReasonsHelp() {
  return (
    <Accordion disableGutters variant="outlined">
      <AccordionSummary expandIcon={<ExpandMore />}>
        <Typography variant="subtitle2">What do quarantine reasons mean?</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Typography variant="body2" color="text.secondary" className="mb-2">
          Quarantined messages are retained as evidence but never update positions, status or
          alerts.
        </Typography>
        <Box component="dl" className="m-0 grid gap-2">
          {(Object.keys(QUARANTINE_REASON_HELP) as QuarantineReason[]).map((r) => (
            <Box key={r}>
              <Typography component="dt" variant="body2" sx={{ fontWeight: 600 }}>
                {humanize(r)}
              </Typography>
              <Typography component="dd" variant="body2" className="m-0">
                {QUARANTINE_REASON_HELP[r]}
              </Typography>
            </Box>
          ))}
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}

/** Ingestion events (accepted / duplicate / quarantined) with filters by status and tracker. */
export function IngestionEventsPanel({
  timeZone,
  status,
  onStatusChange,
  tracker,
  onTrackerChange,
}: IngestionEventsPanelProps) {
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      trackerService.listIngestionEvents(
        { page: q.page, page_size: q.page_size, q: q.q, filters: q.filters },
        signal,
      ),
    [],
  );
  const fetchTrackers = useCallback(
    async (q: string, signal: AbortSignal) =>
      (await trackerService.list({ page: 1, page_size: 20, q }, signal)).items,
    [],
  );
  const columns: DataColumn<IngestionEventDto>[] = [
    {
      id: 'received',
      header: 'Received',
      render: (e) => formatInstantIn(e.received_at, timeZone, true),
    },
    {
      id: 'event',
      header: 'Event time',
      render: (e) => formatInstantIn(e.event_time, timeZone, true),
    },
    {
      id: 'status',
      header: 'Status',
      render: (e) => <StatusChip status={e.status} tones={INGESTION_STATUS_TONES} />,
    },
    {
      id: 'reason',
      header: 'Quarantine reason',
      render: (e) => <QuarantineReasonCell reason={e.quarantine_reason} />,
    },
    { id: 'device', header: 'Device id', render: (e) => e.external_device_id ?? '—' },
    { id: 'tracker', header: 'Tracker', render: (e) => e.tracker_id?.slice(0, 8) ?? '—' },
    { id: 'detail', header: 'Detail', render: (e) => e.detail ?? '—' },
  ];
  const filters = { status: status === '' ? undefined : status, tracker_id: tracker?.id };

  return (
    <Box className="flex flex-col gap-3">
      <QuarantineReasonsHelp />
      <ServerDataTable<IngestionEventDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(e) => e.id}
        filters={filters}
        searchable={false}
        emptyTitle="No ingestion events"
        emptyDescription="Telemetry messages received from trackers appear here."
        toolbar={
          <>
            <TextField
              select
              size="small"
              label="Status"
              value={status}
              onChange={(e) => {
                onStatusChange(e.target.value);
              }}
              sx={{ minWidth: 200 }}
            >
              <MenuItem value="">All statuses</MenuItem>
              {INGESTION_STATUS_OPTIONS.map((o) => (
                <MenuItem key={o.value} value={o.value}>
                  {o.label}
                </MenuItem>
              ))}
            </TextField>
            {tracker !== null ? (
              <Chip
                label={`Tracker: ${tracker.label}`}
                {...(onTrackerChange !== undefined
                  ? {
                      onDelete: () => {
                        onTrackerChange(null);
                      },
                    }
                  : {})}
              />
            ) : (
              <Box sx={{ minWidth: 260 }}>
                <AsyncAutocomplete<TrackerDto>
                  label="Tracker"
                  value={null}
                  fetchOptions={fetchTrackers}
                  getOptionLabel={(t) => `${t.label} (${t.external_id})`}
                  isOptionEqualToValue={(a, b) => a.id === b.id}
                  onChange={(t) => {
                    onTrackerChange?.(t === null ? null : { id: t.id, label: t.label });
                  }}
                />
              </Box>
            )}
          </>
        }
      />
    </Box>
  );
}
