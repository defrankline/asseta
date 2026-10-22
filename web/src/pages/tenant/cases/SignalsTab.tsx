import { Box } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { initialFilter } from '../../../navigation/urlFilters';
import { caseService, riskSignalService } from '../../../api/services/caseService';
import type { MachineDto, RiskSignalDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { explainRiskSignal, RULE_LABELS } from '../../../components/intelligence/signalText';
import { caseDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { formatInstantIn } from '../../../utils/time';
import { MachinePicker } from '../shared/MachinePicker';
import { useStaffLabels } from '../shared/useFinanceLabels';
import { useMachineLabels } from '../shared/useMachineLabels';
import {
  RULE_OPTIONS,
  SEVERITY_FILTER_OPTIONS,
  SEVERITY_LABELS,
  SEVERITY_TONES,
  SIGNAL_STATUS_LABELS,
  SIGNAL_STATUS_OPTIONS,
  SIGNAL_STATUS_TONES,
} from './caseDisplay';
import { SubjectLabel } from './SubjectLabel';

/** Cases checked (newest first) when looking for the one a signal is linked to. */
const CASE_LOOKUP_LIMIT = 10;

/**
 * The case a LINKED signal belongs to: cases share the signal's subject, and the case detail lists the
 * risk-signal ids it holds. Null when not found.
 */
async function findCaseForSignal(s: RiskSignalDto): Promise<string | null> {
  const cases = await caseService.list({
    page: 1,
    page_size: CASE_LOOKUP_LIMIT,
    filters: { subject_type: s.subject_type, subject_id: s.subject_id },
  });
  for (const c of cases.items) {
    const detail = await caseService.get(c.id);
    if (detail.signals.some((x) => x.source_type === 'RISK_SIGNAL' && x.source_id === s.id)) {
      return c.id;
    }
  }
  return null;
}

const shorten = (text: string, max = 160) => (text.length > max ? `${text.slice(0, max)}…` : text);

/** Deterministic risk signals with their evidence summary; a linked signal opens its case. */
export function SignalsTab({ timeZone }: { timeZone: string }) {
  const navigate = useNavigate();
  const notify = useNotify();
  const machineName = useMachineLabels();
  const staffName = useStaffLabels();
  const [rule, setRule] = useState('');
  const [params] = useSearchParams();
  const [severity, setSeverity] = useState(() =>
    initialFilter(params, 'severity', SEVERITY_FILTER_OPTIONS, ''),
  );
  const [status, setStatus] = useState('');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const liveReload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  // New signals are announced through the cases they open or join.
  useLiveRefresh([ENTITY.anomalyCase], liveReload);
  const filters = useMemo(
    () => ({
      rule_code: rule || undefined,
      severity: severity || undefined,
      status: status || undefined,
      machine_id: machine?.id,
    }),
    [rule, severity, status, machine],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      riskSignalService.list(
        { page: q.page, page_size: q.page_size, q: q.q, filters: q.filters },
        signal,
      ),
    [],
  );
  const openCase = (s: RiskSignalDto) => {
    if (s.status !== 'LINKED') return;
    findCaseForSignal(s)
      .then((caseId) => {
        if (caseId === null) notify.info('The case for this signal could not be found.');
        else void navigate(caseDetailPath(caseId));
      })
      .catch((err: unknown) => {
        notify.error(err, 'Could not open the case for this signal.');
      });
  };
  const columns: DataColumn<RiskSignalDto>[] = [
    { id: 'rule', header: 'Signal', render: (s) => RULE_LABELS[s.rule_code] },
    {
      id: 'severity',
      header: 'Severity',
      render: (s) => (
        <StatusChip
          status={s.severity}
          tones={SEVERITY_TONES}
          label={SEVERITY_LABELS[s.severity]}
        />
      ),
    },
    {
      id: 'subject',
      header: 'Subject',
      render: (s) => (
        <SubjectLabel
          subjectType={s.subject_type}
          subjectId={s.subject_id}
          machineName={machineName}
          staffName={staffName}
        />
      ),
    },
    {
      id: 'window',
      header: 'Observed',
      render: (s) =>
        `${formatInstantIn(s.window_start, timeZone)} – ${formatInstantIn(s.window_end, timeZone)}`,
    },
    {
      id: 'evidence',
      header: 'What was recorded',
      render: (s) => shorten(explainRiskSignal(s.rule_code, s.evidence, timeZone)),
    },
    {
      id: 'status',
      header: 'Status',
      render: (s) => (
        <StatusChip
          status={s.status}
          tones={SIGNAL_STATUS_TONES}
          label={SIGNAL_STATUS_LABELS[s.status]}
        />
      ),
    },
  ];
  return (
    <ServerDataTable<RiskSignalDto>
      columns={columns}
      fetchPage={fetchPage}
      getRowId={(s) => s.id}
      filters={filters}
      searchPlaceholder="Search rule"
      emptyTitle="No signals match these filters"
      reloadKey={reloadKey}
      isRowMuted={(s) => s.status === 'DISMISSED'}
      onRowClick={openCase}
      toolbar={
        <>
          <StaticSelectFilter
            label="Signal"
            value={rule}
            options={RULE_OPTIONS}
            onChange={setRule}
            allLabel="All signals"
            minWidth={240}
          />
          <StaticSelectFilter
            label="Severity"
            value={severity}
            options={SEVERITY_FILTER_OPTIONS}
            onChange={setSeverity}
            allLabel="All severities"
          />
          <StaticSelectFilter
            label="Status"
            value={status}
            options={SIGNAL_STATUS_OPTIONS}
            onChange={setStatus}
            allLabel="All statuses"
          />
          <Box className="min-w-56">
            <MachinePicker value={machine} onChange={setMachine} />
          </Box>
        </>
      }
    />
  );
}
