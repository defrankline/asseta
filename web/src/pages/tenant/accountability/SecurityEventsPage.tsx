import { Box, Paper, TextField } from '@mui/material';
import dayjs from 'dayjs';
import { useCallback, useState } from 'react';
import { useSearchParams } from 'react-router';
import { accountabilityService } from '../../../api/services/accountabilityService';
import type { SecurityEventDto, SecurityEventKind } from '../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip, type StatusTone } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { initialFilter } from '../../../navigation/urlFilters';
import { isIsoDate } from '../../../utils/dates';
import { formatInstantIn } from '../../../utils/time';
import { PersonName } from '../shared/PersonName';

const EVENT_KIND_LABELS: Readonly<Record<SecurityEventKind, string>> = {
  PERMISSION_DENIED: 'Missing permission',
  SEGREGATION_OF_DUTIES: 'Own record (segregation of duties)',
};
const EVENT_KIND_TONES: Readonly<Record<SecurityEventKind, StatusTone>> = {
  PERMISSION_DENIED: 'warning',
  SEGREGATION_OF_DUTIES: 'info',
};
const KIND_OPTIONS = (Object.keys(EVENT_KIND_LABELS) as SecurityEventKind[]).map((k) => ({
  value: k,
  label: EVENT_KIND_LABELS[k],
}));

const chip = (e: SecurityEventDto) => (
  <StatusChip status={e.kind} tones={EVENT_KIND_TONES} label={EVENT_KIND_LABELS[e.kind]} />
);

function Actor({ e }: { e: SecurityEventDto }) {
  if (e.actor_display_name !== null && e.actor_display_name !== undefined)
    return <>{e.actor_display_name}</>;
  return <PersonName userId={e.actor_user_id} empty={e.actor_subject ?? '—'} />;
}

/** Day boundaries (local) as instants for the API; empty or invalid dates send nothing. */
const dayStart = (d: string) => (isIsoDate(d) ? dayjs(d).startOf('day').toISOString() : undefined);
const dayEnd = (d: string) =>
  isIsoDate(d) ? dayjs(d).add(1, 'day').startOf('day').toISOString() : undefined;

/** Refused attempts (missing permission, deciding your own record), latest first. Read-only. */
export function SecurityEventsPage() {
  const timeZone = useDisplayTimeZone();
  const [params] = useSearchParams();
  const [kind, setKind] = useState(() => initialFilter(params, 'kind', KIND_OPTIONS, ''));
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [viewing, setViewing] = useState<SecurityEventDto | null>(null);
  const fetchPage = useCallback<FetchPage<SecurityEventDto>>(
    (query, signal) => accountabilityService.securityEvents(query, signal),
    [],
  );
  const columns: DataColumn<SecurityEventDto>[] = [
    { id: 'at', header: 'When', render: (e) => formatInstantIn(e.occurred_at, timeZone) },
    { id: 'kind', header: 'Kind', render: chip },
    { id: 'who', header: 'Who', render: (e) => <Actor e={e} /> },
    { id: 'what', header: 'Attempted', render: (e) => e.action ?? e.permission ?? '—' },
    {
      id: 'record',
      header: 'Record',
      render: (e) => (e.entity_type === null ? '—' : e.entity_type.replace(/_/g, ' ')),
    },
    {
      id: 'request',
      header: 'Request',
      render: (e) =>
        e.request_path === null ? '—' : `${e.request_method ?? ''} ${e.request_path}`.trim(),
    },
  ];
  return (
    <>
      <PageHeader
        title="Security events"
        subtitle="Attempts the system refused: a missing permission, or someone deciding their own record"
      />
      <Paper variant="outlined" className="p-3">
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(e) => e.id}
          searchPlaceholder="Search permission, action, record or path"
          filters={{
            kind: kind || undefined,
            occurred_from: dayStart(from),
            occurred_to: dayEnd(to),
          }}
          emptyTitle="No refused attempts"
          onRowClick={setViewing}
          toolbar={
            <Box className="flex flex-wrap items-center gap-3">
              <StaticSelectFilter
                label="Kind"
                value={kind}
                options={KIND_OPTIONS}
                onChange={setKind}
              />
              <TextField
                size="small"
                type="date"
                label="From"
                value={from}
                onChange={(e) => {
                  setFrom(e.target.value);
                }}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField
                size="small"
                type="date"
                label="To"
                value={to}
                onChange={(e) => {
                  setTo(e.target.value);
                }}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Box>
          }
        />
      </Paper>
      {viewing !== null && (
        <DetailsDrawer
          title="Refused attempt"
          status={chip(viewing)}
          onClose={() => {
            setViewing(null);
          }}
        >
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'When', value: formatInstantIn(viewing.occurred_at, timeZone) },
              { label: 'Who', value: <Actor e={viewing} /> },
              { label: 'Permission', value: viewing.permission ?? '—' },
              { label: 'Action', value: viewing.action ?? '—' },
              { label: 'Record type', value: viewing.entity_type ?? '—' },
              { label: 'Record id', value: viewing.entity_id ?? '—' },
              { label: 'Method', value: viewing.request_method ?? '—' },
              { label: 'Path', value: viewing.request_path ?? '—' },
            ]}
          />
          {Object.keys(viewing.detail).length > 0 && (
            <Box
              component="pre"
              aria-label="Details"
              sx={{ m: 0, p: 1.5, bgcolor: 'action.hover', borderRadius: 1, overflowX: 'auto' }}
            >
              {JSON.stringify(viewing.detail, null, 2)}
            </Box>
          )}
        </DetailsDrawer>
      )}
    </>
  );
}
