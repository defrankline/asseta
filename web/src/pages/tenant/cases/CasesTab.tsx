import { Box } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { caseService } from '../../../api/services/caseService';
import type { AnomalyCaseDto, MachineDto, PersonDto } from '../../../api/types';
import { AsyncAutocomplete } from '../../../components/data/AsyncAutocomplete';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { caseDetailPath } from '../../../navigation/routes';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { formatInstantIn } from '../../../utils/time';
import { MachinePicker } from '../shared/MachinePicker';
import { PersonName } from '../shared/PersonName';
import { useStaffLabels } from '../shared/useFinanceLabels';
import { useMachineLabels } from '../shared/useMachineLabels';
import {
  CASE_STATUS_LABELS,
  CASE_STATUS_OPTIONS,
  CASE_STATUS_TONES,
  personLabel,
  searchPeople,
  SEVERITY_FILTER_OPTIONS,
  SEVERITY_LABELS,
  SEVERITY_TONES,
} from './caseDisplay';
import { SubjectLabel } from './SubjectLabel';

/** Investigation cases with server filters; opens the case on row click. Live-refreshed on case changes. */
export function CasesTab({ timeZone }: { timeZone: string }) {
  const navigate = useNavigate();
  const machineName = useMachineLabels();
  const staffName = useStaffLabels();
  const [status, setStatus] = useState('OPEN');
  const [severity, setSeverity] = useState('');
  const [assignee, setAssignee] = useState<PersonDto | null>(null);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const liveReload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  useLiveRefresh([ENTITY.anomalyCase], liveReload);
  const filters = useMemo(
    () => ({
      status: status || undefined,
      severity: severity || undefined,
      assignee_user_id: assignee?.user_id,
      machine_id: machine?.id,
    }),
    [status, severity, assignee, machine],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      caseService.list(
        { page: q.page, page_size: q.page_size, q: q.q, filters: q.filters },
        signal,
      ),
    [],
  );
  const columns: DataColumn<AnomalyCaseDto>[] = [
    { id: 'number', header: 'Case', render: (c) => c.case_number },
    { id: 'title', header: 'Title', render: (c) => c.title },
    {
      id: 'subject',
      header: 'Subject',
      render: (c) => (
        <SubjectLabel
          subjectType={c.subject_type}
          subjectId={c.subject_id}
          machineName={machineName}
          staffName={staffName}
        />
      ),
    },
    {
      id: 'severity',
      header: 'Severity',
      render: (c) => (
        <StatusChip
          status={c.severity}
          tones={SEVERITY_TONES}
          label={SEVERITY_LABELS[c.severity]}
        />
      ),
    },
    {
      id: 'status',
      header: 'Status',
      render: (c) => (
        <StatusChip
          status={c.status}
          tones={CASE_STATUS_TONES}
          label={CASE_STATUS_LABELS[c.status]}
        />
      ),
    },
    {
      id: 'assignee',
      header: 'Assignee',
      render: (c) => <PersonName userId={c.assignee_user_id} empty="Unassigned" />,
    },
    { id: 'signals', header: 'Signals', align: 'right', render: (c) => c.signal_count },
    { id: 'opened', header: 'Opened', render: (c) => formatInstantIn(c.opened_at, timeZone) },
    {
      id: 'last',
      header: 'Last signal',
      render: (c) => formatInstantIn(c.last_signal_at, timeZone),
    },
  ];
  return (
    <ServerDataTable<AnomalyCaseDto>
      columns={columns}
      fetchPage={fetchPage}
      getRowId={(c) => c.id}
      filters={filters}
      searchPlaceholder="Search case number or title"
      emptyTitle="No cases match these filters"
      reloadKey={reloadKey}
      isRowMuted={(c) => c.status === 'RESOLVED'}
      onRowClick={(c) => {
        void navigate(caseDetailPath(c.id));
      }}
      toolbar={
        <>
          <StaticSelectFilter
            label="Status"
            value={status}
            options={CASE_STATUS_OPTIONS}
            onChange={setStatus}
            allLabel="All statuses"
          />
          <StaticSelectFilter
            label="Severity"
            value={severity}
            options={SEVERITY_FILTER_OPTIONS}
            onChange={setSeverity}
            allLabel="All severities"
          />
          <Box className="min-w-56">
            <AsyncAutocomplete<PersonDto>
              label="Assignee"
              value={assignee}
              onChange={setAssignee}
              fetchOptions={searchPeople}
              getOptionLabel={personLabel}
              isOptionEqualToValue={(a, b) => a.user_id === b.user_id}
            />
          </Box>
          <Box className="min-w-56">
            <MachinePicker value={machine} onChange={setMachine} />
          </Box>
        </>
      }
    />
  );
}
