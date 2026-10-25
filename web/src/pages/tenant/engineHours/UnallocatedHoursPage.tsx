import { Box, Button, Chip, Link, TextField } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { engineHoursService } from '../../../api/services/engineHoursService';
import type { MachineDto, UnallocatedSegmentDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useDebouncedValue } from '../../../hooks/useDebouncedValue';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { engineHoursMachinePath, ROUTES } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { MachineFilter } from '../shared/financePickers';
import { machineText } from '../shared/names';
import { ClassifyHoursDialog, type SegmentRef } from './ClassifyHoursDialog';
import {
  CLASSIFICATION_LABELS,
  CLASSIFICATION_TONES,
  OUTCOME_LABELS,
  SEGMENT_FILTER_OPTIONS,
  sourceLabel,
} from './engineHoursDisplay';

const segmentKey = (s: UnallocatedSegmentDto) => `${s.start.ref}:${s.end.ref}`;

/**
 * Engine hours outside customer work across the fleet, oldest first. By default the open items:
 * verified readings, not yet explained. Explaining them never depends on how old they are.
 */
export function UnallocatedHoursPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const canExplain = useCanMutate(PERMISSIONS.tenantMeterReview);
  const [classification, setClassification] = useState('');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [minAge, setMinAge] = useState('');
  const minAgeDays = useDebouncedValue(/^\d+$/.test(minAge.trim()) ? minAge.trim() : '', 300);
  const [explaining, setExplaining] = useState<SegmentRef | null>(null);
  const navigate = useNavigate();
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<UnallocatedSegmentDto>>(
    (query, signal) => engineHoursService.listUnallocated(query, signal),
    [],
  );
  const columns: DataColumn<UnallocatedSegmentDto>[] = [
    {
      id: 'machine',
      header: 'Machine',
      render: (s) => (
        <Link
          component={RouterLink}
          to={engineHoursMachinePath(s.machine_id)}
          onClick={(e) => {
            e.stopPropagation();
          }}
        >
          {machineText(s.machine_code, s.machine_name, s.machine_id)}
        </Link>
      ),
    },
    {
      id: 'period',
      header: 'Between readings',
      render: (s) => (
        <span>
          {s.start.reading} ({sourceLabel(s.start.source)}) → {s.end.reading} (
          {sourceLabel(s.end.source)})
          <br />
          {formatInstantIn(s.start.at, timeZone)} → {formatInstantIn(s.end.at, timeZone)}
        </span>
      ),
    },
    {
      id: 'hours',
      header: 'Hours',
      align: 'right',
      render: (s) => <span className="font-mono">{s.hours}</span>,
    },
    {
      id: 'age',
      header: 'Open for',
      render: (s) => (
        <Box className="flex flex-wrap items-center gap-1">
          {`${String(s.age_days)} day${s.age_days === 1 ? '' : 's'}`}
          {s.investigation_due && s.classification === 'UNEXPLAINED' && (
            <Chip size="small" color="warning" label="Investigation opened" />
          )}
        </Box>
      ),
    },
    {
      id: 'state',
      header: 'State',
      render: (s) => (
        <Box className="flex flex-wrap gap-1">
          <StatusChip
            status={s.classification}
            tones={CLASSIFICATION_TONES}
            label={CLASSIFICATION_LABELS[s.classification]}
          />
          {s.proposal !== null && (
            <Chip
              size="small"
              variant="outlined"
              label={`${OUTCOME_LABELS[s.proposal.outcome]} proposed`}
            />
          )}
          {s.review === 'PENDING_REVIEW' && (
            <Chip size="small" variant="outlined" label="Reading under review" />
          )}
        </Box>
      ),
    },
    {
      id: 'action',
      header: '',
      align: 'right',
      render: (s) => (
        <Box className="flex justify-end gap-1">
          <Button
            size="small"
            component={RouterLink}
            to={engineHoursMachinePath(s.machine_id)}
            onClick={(e) => {
              e.stopPropagation();
            }}
          >
            Ledger
          </Button>
          {canExplain &&
            s.classification === 'UNEXPLAINED' &&
            s.proposal === null &&
            s.review === 'VERIFIED' && (
              <Button
                size="small"
                onClick={() => {
                  setExplaining({
                    machineId: s.machine_id,
                    machineLabel: machineText(s.machine_code, s.machine_name, s.machine_id),
                    start: s.start,
                    end: s.end,
                    hours: s.hours,
                  });
                }}
              >
                Explain
              </Button>
            )}
        </Box>
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Hours to explain"
        subtitle="Engine hours outside customer work, oldest first. Unexplained hours are a question to answer, not a finding."
        actions={
          <Button
            component={RouterLink}
            to={ROUTES.tenantEngineHourClassifications}
            variant="outlined"
          >
            Explanations
          </Button>
        }
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={segmentKey}
        onRowClick={(s) => {
          void navigate(engineHoursMachinePath(s.machine_id));
        }}
        searchPlaceholder="Search machine code or name"
        reloadKey={reloadKey}
        filters={{
          classification: classification || undefined,
          machine_id: machine?.id,
          min_age_days: minAgeDays || undefined,
        }}
        emptyTitle={
          classification === '' ? 'No hours waiting for an explanation' : 'No matching hours'
        }
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="State"
              value={classification}
              options={SEGMENT_FILTER_OPTIONS}
              allLabel="Open items"
              onChange={setClassification}
              minWidth={220}
            />
            <Box sx={{ minWidth: 240 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
            </Box>
            <TextField
              size="small"
              label="Open at least (days)"
              value={minAge}
              onChange={(e) => {
                setMinAge(e.target.value);
              }}
              slotProps={{ htmlInput: { inputMode: 'numeric' } }}
              sx={{ width: 180 }}
            />
          </Box>
        }
      />
      {explaining !== null && (
        <ClassifyHoursDialog
          segment={explaining}
          onClose={() => {
            setExplaining(null);
          }}
          onProposed={(c) => {
            notify.success(
              c.status === 'APPROVED'
                ? 'Hours explained.'
                : 'Explanation proposed; a second person decides it.',
            );
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
