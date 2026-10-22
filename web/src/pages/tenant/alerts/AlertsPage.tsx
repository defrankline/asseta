import { Alert, Tooltip } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';
import { alertService } from '../../../api/services/alertService';
import { fleetService } from '../../../api/services/fleetService';
import type { AlertDto, MachineDto } from '../../../api/types';
import { ExportMenu } from '../../../components/data/ExportMenu';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import {
  ALERT_SEVERITY_TONES,
  ALERT_SEVERITY_OPTIONS,
  ALERT_STATUS_OPTIONS,
  ALERT_STATUS_TONES,
  ALERT_TYPE_OPTIONS,
  labelOf,
  machineLabel,
  SUPERSEDED_HELP,
} from '../shared/display';
import { MachinePicker } from '../shared/MachinePicker';
import { AlertDetailDialog } from './AlertDetailDialog';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { initialFilter } from '../../../navigation/urlFilters';

/** Tracking alerts: server-filtered list, evidence detail, acknowledge / resolve. */
export function AlertsPage() {
  const tz = useDisplayTimeZone();
  const notify = useNotify();
  const [params] = useSearchParams();
  const [status, setStatus] = useState(() =>
    initialFilter(params, 'status', ALERT_STATUS_OPTIONS, 'OPEN'),
  );
  const [type, setType] = useState(() =>
    initialFilter(params, 'alert_type', ALERT_TYPE_OPTIONS, ''),
  );
  const [severity, setSeverity] = useState(() =>
    initialFilter(params, 'severity', ALERT_SEVERITY_OPTIONS, ''),
  );
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [selected, setSelected] = useState<AlertDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const liveReload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  useLiveRefresh([ENTITY.alert], liveReload);

  // Machine labels for the table (the alert DTO carries only machine_id).
  const loadFleet = useCallback((signal: AbortSignal) => fleetService.map(signal), []);
  const fleet = useAsyncResource(loadFleet);
  const labels = useMemo(
    () => new Map((fleet.data ?? []).map((m) => [m.machine_id, machineLabel(m)])),
    [fleet.data],
  );

  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) => alertService.list(q, signal),
    [],
  );
  const filters = useMemo(
    () => ({ status, alert_type: type, severity, machine_id: machine?.id }),
    [status, type, severity, machine],
  );

  const columns: DataColumn<AlertDto>[] = [
    { id: 'time', header: 'Event time', render: (a) => formatInstantIn(a.event_time, tz) },
    {
      id: 'severity',
      header: 'Severity',
      render: (a) => <StatusChip status={a.severity} tones={ALERT_SEVERITY_TONES} />,
    },
    { id: 'type', header: 'Type', render: (a) => labelOf(ALERT_TYPE_OPTIONS, a.alert_type) },
    { id: 'title', header: 'Title', render: (a) => a.title },
    {
      id: 'machine',
      header: 'Machine',
      render: (a) => (a.machine_id === null ? '—' : (labels.get(a.machine_id) ?? a.machine_id)),
    },
    {
      id: 'status',
      header: 'Status',
      render: (a) =>
        a.status === 'SUPERSEDED' ? (
          <Tooltip title={SUPERSEDED_HELP}>
            <span>
              <StatusChip status={a.status} tones={ALERT_STATUS_TONES} />
            </span>
          </Tooltip>
        ) : (
          <StatusChip status={a.status} tones={ALERT_STATUS_TONES} />
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Alerts"
        subtitle={`Tracking alerts · times in ${tz}`}
        actions={<ExportMenu reports={[{ code: 'alerts', filters }]} />}
      />
      {status === 'SUPERSEDED' && (
        <Alert severity="info" className="mb-3">
          {SUPERSEDED_HELP}
        </Alert>
      )}
      <ServerDataTable<AlertDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(a) => a.id}
        filters={filters}
        searchPlaceholder="Search alerts"
        emptyTitle="No alerts match these filters"
        reloadKey={reloadKey}
        onRowClick={setSelected}
        toolbar={
          <>
            <StaticSelectFilter
              label="Status"
              value={status}
              options={ALERT_STATUS_OPTIONS}
              onChange={setStatus}
            />
            <StaticSelectFilter
              label="Type"
              value={type}
              options={ALERT_TYPE_OPTIONS}
              onChange={setType}
            />
            <StaticSelectFilter
              label="Severity"
              value={severity}
              options={ALERT_SEVERITY_OPTIONS}
              onChange={setSeverity}
            />
            <div className="min-w-64">
              <MachinePicker label="Machine" value={machine} onChange={setMachine} />
            </div>
          </>
        }
      />
      {selected !== null && (
        <AlertDetailDialog
          alert={selected}
          machineLabel={
            selected.machine_id === null ? null : (labels.get(selected.machine_id) ?? null)
          }
          timeZone={tz}
          onClose={() => {
            setSelected(null);
          }}
          onChanged={(a) => {
            notify.success(a.status === 'RESOLVED' ? 'Alert resolved.' : 'Alert acknowledged.');
            setSelected(a);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
