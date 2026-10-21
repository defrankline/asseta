import Add from '@mui/icons-material/Add';
import { Box, Button, MenuItem, Paper, Tab, Tabs, TextField } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { CanMutate } from '../../../access/CanMutate';
import { trackerService } from '../../../api/services/trackerService';
import type { TrackerDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { AgeText } from '../../../components/display/AgeText';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNow } from '../../../hooks/useNow';
import { useNotify } from '../../../notifications/useNotify';
import { TRACKER_STATE_OPTIONS, TRACKER_STATE_TONES } from '../shared/display';
import { IngestionEventsPanel, type TrackerFilter } from './IngestionEventsPanel';
import { RegisterTrackerDialog } from './RegisterTrackerDialog';
import { TrackerDrawer } from './TrackerDrawer';

type TabKey = 'trackers' | 'events';

/** Tracker registry, capabilities, assignments and ingestion/quarantine events. */
export function TrackersPage() {
  const notify = useNotify();
  const tz = useDisplayTimeZone();
  const now = useNow();
  const [tab, setTab] = useState<TabKey>('trackers');
  const [state, setState] = useState('');
  const [registering, setRegistering] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [eventStatus, setEventStatus] = useState('');
  const [eventTracker, setEventTracker] = useState<TrackerFilter | null>(null);

  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      trackerService.list(
        { page: q.page, page_size: q.page_size, q: q.q, filters: q.filters },
        signal,
      ),
    [],
  );

  const columns: DataColumn<TrackerDto>[] = [
    { id: 'label', header: 'Label', render: (t) => <strong>{t.label}</strong> },
    { id: 'external', header: 'External id', render: (t) => t.external_id },
    {
      id: 'state',
      header: 'State',
      render: (t) => <StatusChip status={t.provisioning_state} tones={TRACKER_STATE_TONES} />,
    },
    {
      id: 'last',
      header: 'Last report',
      render: (t) => <AgeText at={t.last_report_at} now={now} timeZone={tz} />,
    },
    {
      id: 'assignment',
      header: 'Current assignment',
      render: (t) => {
        const a = t.current_assignment ?? null;
        if (a === null) return 'Unassigned';
        return `Machine ${a.machine_id.slice(0, 8)}${a.is_primary ? ' · primary' : ''}`;
      },
    },
    {
      id: 'sim',
      header: 'SIM / carrier',
      render: (t) =>
        [t.sim_msisdn ?? t.sim_iccid, t.carrier].filter((x) => x !== null).join(' · ') || '—',
    },
  ];

  return (
    <>
      <PageHeader
        title="Trackers"
        subtitle="Machine-mounted GPS/telematics devices, capabilities and ingestion"
        actions={
          <CanMutate permission={PERMISSIONS.tenantTrackerWrite}>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setRegistering(true);
              }}
            >
              Register tracker
            </Button>
          </CanMutate>
        }
      />
      <Paper variant="outlined" className="mb-3">
        <Tabs
          value={tab}
          onChange={(_e, v: TabKey) => {
            setTab(v);
          }}
          aria-label="Tracker views"
        >
          <Tab value="trackers" label="Trackers" />
          <Tab value="events" label="Ingestion events" />
        </Tabs>
      </Paper>
      {tab === 'trackers' ? (
        <ServerDataTable<TrackerDto>
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(t) => t.id}
          filters={{ state: state === '' ? undefined : state }}
          searchPlaceholder="Search label or device id"
          emptyTitle="No trackers registered"
          reloadKey={reloadKey}
          onRowClick={(t) => {
            setSelected(t.id);
          }}
          toolbar={
            <TextField
              select
              size="small"
              label="State"
              value={state}
              onChange={(e) => {
                setState(e.target.value);
              }}
              sx={{ minWidth: 200 }}
            >
              <MenuItem value="">All states</MenuItem>
              {TRACKER_STATE_OPTIONS.map((o) => (
                <MenuItem key={o.value} value={o.value}>
                  {o.label}
                </MenuItem>
              ))}
            </TextField>
          }
        />
      ) : (
        <Box>
          <IngestionEventsPanel
            timeZone={tz}
            status={eventStatus}
            onStatusChange={setEventStatus}
            tracker={eventTracker}
            onTrackerChange={setEventTracker}
          />
        </Box>
      )}
      {registering && (
        <RegisterTrackerDialog
          onClose={() => {
            setRegistering(false);
          }}
          onRegistered={(t) => {
            notify.success(`Tracker ${t.label} registered.`);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
      {selected !== null && (
        <TrackerDrawer
          trackerId={selected}
          onClose={() => {
            setSelected(null);
          }}
          onChanged={() => {
            setReloadKey((k) => k + 1);
          }}
          onViewEvents={(t) => {
            setEventTracker({ id: t.id, label: t.label });
            setSelected(null);
            setTab('events');
          }}
        />
      )}
    </>
  );
}
