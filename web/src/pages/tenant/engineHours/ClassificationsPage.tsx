import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { engineHoursService } from '../../../api/services/engineHoursService';
import type { ClassificationDto, MachineDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { engineHoursMachinePath, ROUTES } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { MachineFilter } from '../shared/financePickers';
import { PersonName } from '../shared/PersonName';
import { DecideClassificationDialog } from './DecideDialogs';
import {
  hoursText,
  OUTCOME_LABELS,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_STATUS_OPTIONS,
  PROPOSAL_STATUS_TONES,
} from './engineHoursDisplay';
import { DecideButton } from './MeterDecisionDialog';

const machineOf = (c: ClassificationDto) => c.machine_code ?? `${c.machine_id.slice(0, 8)}…`;

/** Explanations of unallocated engine hours (non-customer activity or identified variance) and their decisions. */
export function ClassificationsPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const canDecide = useCanMutate(PERMISSIONS.tenantMeterClassify);
  const [status, setStatus] = useState('PROPOSED');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [viewing, setViewing] = useState<ClassificationDto | null>(null);
  const [deciding, setDeciding] = useState<ClassificationDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<ClassificationDto>>(
    (query, signal) => engineHoursService.listClassifications(query, signal),
    [],
  );
  const decideAction = (c: ClassificationDto) =>
    canDecide && c.status === 'PROPOSED' ? (
      <DecideButton
        proposedBy={c.proposed_by}
        onClick={() => {
          setViewing(null);
          setDeciding(c);
        }}
      />
    ) : null;
  const columns: DataColumn<ClassificationDto>[] = [
    { id: 'machine', header: 'Machine', render: machineOf },
    {
      id: 'period',
      header: 'Period',
      render: (c) =>
        `${formatInstantIn(c.start_at, timeZone)} → ${formatInstantIn(c.end_at, timeZone)}`,
    },
    {
      id: 'hours',
      header: 'Hours',
      align: 'right',
      render: (c) => <span className="font-mono">{c.hours}</span>,
    },
    { id: 'outcome', header: 'Explained as', render: (c) => OUTCOME_LABELS[c.outcome] },
    { id: 'reason', header: 'Category / reason', render: (c) => c.reason_name ?? '—' },
    { id: 'by', header: 'Proposed by', render: (c) => <PersonName userId={c.proposed_by} /> },
    {
      id: 'status',
      header: 'Status',
      render: (c) => (
        <StatusChip
          status={c.status}
          tones={PROPOSAL_STATUS_TONES}
          label={PROPOSAL_STATUS_LABELS[c.status]}
        />
      ),
    },
    { id: 'decide', header: '', align: 'right', render: decideAction },
  ];
  return (
    <>
      <PageHeader
        title="Hour explanations"
        subtitle="Unallocated engine hours explained as non-customer activity or an identified variance"
        actions={
          <Button
            component={RouterLink}
            to={ROUTES.tenantEngineHoursUnallocated}
            variant="outlined"
          >
            Hours to explain
          </Button>
        }
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(c) => c.id}
        searchPlaceholder="Search machine code or name"
        reloadKey={reloadKey}
        filters={{ status: status || undefined, machine_id: machine?.id }}
        emptyTitle={
          status === 'PROPOSED' ? 'No explanations awaiting a decision' : 'No explanations'
        }
        isRowMuted={(c) => c.status === 'REJECTED'}
        onRowClick={setViewing}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={PROPOSAL_STATUS_OPTIONS}
              allLabel="All statuses"
              onChange={setStatus}
            />
            <Box sx={{ minWidth: 240 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
            </Box>
          </Box>
        }
      />
      {viewing !== null && (
        <DetailsDrawer
          title={`Explanation · ${hoursText(viewing.hours)} · ${machineOf(viewing)}`}
          status={
            <StatusChip
              status={viewing.status}
              tones={PROPOSAL_STATUS_TONES}
              label={PROPOSAL_STATUS_LABELS[viewing.status]}
            />
          }
          actions={
            <Box className="flex flex-wrap gap-2">
              <Button component={RouterLink} to={engineHoursMachinePath(viewing.machine_id)}>
                Engine hours
              </Button>
              {decideAction(viewing)}
            </Box>
          }
          onClose={() => {
            setViewing(null);
          }}
        >
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Hours', value: hoursText(viewing.hours) },
              { label: 'From', value: formatInstantIn(viewing.start_at, timeZone) },
              { label: 'To', value: formatInstantIn(viewing.end_at, timeZone) },
              { label: 'Explained as', value: OUTCOME_LABELS[viewing.outcome] },
              { label: 'Category / reason', value: viewing.reason_name ?? '—' },
              { label: 'What happened', value: viewing.note },
              { label: 'Proposed by', value: <PersonName userId={viewing.proposed_by} /> },
              { label: 'Proposed', value: formatInstantIn(viewing.proposed_at, timeZone) },
              { label: 'Decided by', value: <PersonName userId={viewing.decided_by} /> },
              { label: 'Decided', value: formatInstantIn(viewing.decided_at, timeZone) },
              { label: 'Decision note', value: viewing.decision_note ?? '—' },
              { label: 'Policy', value: viewing.policy_version },
            ]}
          />
        </DetailsDrawer>
      )}
      {deciding !== null && (
        <DecideClassificationDialog
          classification={deciding}
          timeZone={timeZone}
          onClose={() => {
            setDeciding(null);
          }}
          onDecided={(c) => {
            notify.success(`Explanation ${PROPOSAL_STATUS_LABELS[c.status].toLowerCase()}.`);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
