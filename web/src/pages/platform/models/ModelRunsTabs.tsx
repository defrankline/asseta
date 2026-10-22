import { Box, Paper, Tab, Tabs } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { platformMlService } from '../../../api/services/platformMlService';
import type { MlInferenceAuditDto, MlPredictionDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { formatInstantIn } from '../../../utils/time';
import {
  DECISION_LABELS,
  DECISION_OPTIONS,
  DECISION_TONES,
  OUTCOME_OPTIONS,
  OUTCOME_TONES,
  scoreText,
} from './modelDisplay';

type RunsTab = 'predictions' | 'audit';

function PredictionsTable({ modelId, timeZone }: { modelId: string; timeZone: string }) {
  const [state, setState] = useState('');
  const filters = useMemo(
    () => ({ model_version_id: modelId, decision_state: state || undefined }),
    [modelId, state],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      platformMlService.listPredictions(
        { page: q.page, page_size: q.page_size, filters: q.filters },
        signal,
      ),
    [],
  );
  const columns: DataColumn<MlPredictionDto>[] = [
    { id: 'asOf', header: 'Week ending', render: (p) => formatInstantIn(p.as_of, timeZone) },
    { id: 'subject', header: 'Machine', render: (p) => `${p.subject_id.slice(0, 8)}…` },
    {
      id: 'state',
      header: 'Decision',
      render: (p) => (
        <StatusChip
          status={p.decision_state}
          tones={DECISION_TONES}
          label={DECISION_LABELS[p.decision_state]}
        />
      ),
    },
    { id: 'score', header: 'Score', render: scoreText },
    {
      id: 'features',
      header: 'Features present',
      align: 'right',
      render: (p) => p.features_present,
    },
    {
      id: 'explanations',
      header: 'Explanations',
      render: (p) => (p.explanations.length === 0 ? '—' : p.explanations.join(' ')),
    },
    { id: 'case', header: 'Case', render: (p) => (p.case_id === null ? '—' : 'Linked') },
  ];
  return (
    <ServerDataTable<MlPredictionDto>
      columns={columns}
      fetchPage={fetchPage}
      getRowId={(p) => p.id}
      filters={filters}
      searchable={false}
      emptyTitle="No predictions for this version"
      toolbar={
        <StaticSelectFilter
          label="Decision"
          value={state}
          options={DECISION_OPTIONS}
          onChange={setState}
          allLabel="All decisions"
        />
      }
    />
  );
}

function AuditTable({ modelId, timeZone }: { modelId: string; timeZone: string }) {
  const [outcome, setOutcome] = useState('');
  const filters = useMemo(
    () => ({ model_version_id: modelId, outcome: outcome || undefined }),
    [modelId, outcome],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      platformMlService.listInferenceAudit(
        { page: q.page, page_size: q.page_size, filters: q.filters },
        signal,
      ),
    [],
  );
  const columns: DataColumn<MlInferenceAuditDto>[] = [
    { id: 'at', header: 'Started', render: (a) => formatInstantIn(a.started_at, timeZone) },
    {
      id: 'outcome',
      header: 'Outcome',
      render: (a) => <StatusChip status={a.outcome} tones={OUTCOME_TONES} />,
    },
    { id: 'latency', header: 'Latency (ms)', align: 'right', render: (a) => a.latency_ms },
    { id: 'input', header: 'Input rows', align: 'right', render: (a) => a.input_rows },
    { id: 'written', header: 'Predictions', align: 'right', render: (a) => a.predictions_written },
    { id: 'surfaced', header: 'Surfaced', align: 'right', render: (a) => a.surfaced },
    { id: 'reason', header: 'Reason', render: (a) => a.reason ?? '—' },
  ];
  return (
    <ServerDataTable<MlInferenceAuditDto>
      columns={columns}
      fetchPage={fetchPage}
      getRowId={(a) => a.id}
      filters={filters}
      searchable={false}
      emptyTitle="No inference runs for this version"
      toolbar={
        <StaticSelectFilter
          label="Outcome"
          value={outcome}
          options={OUTCOME_OPTIONS}
          onChange={setOutcome}
          allLabel="All outcomes"
        />
      }
    />
  );
}

/** Platform predictions and the inference audit log, filtered to one model version. */
export function ModelRunsTabs({ modelId, timeZone }: { modelId: string; timeZone: string }) {
  const [tab, setTab] = useState<RunsTab>('predictions');
  return (
    <Paper variant="outlined" component="section" aria-label="Predictions and runs">
      <Tabs
        value={tab}
        aria-label="Predictions and runs"
        onChange={(_e, v: RunsTab) => {
          setTab(v);
        }}
      >
        <Tab value="predictions" label="Predictions" />
        <Tab value="audit" label="Inference runs" />
      </Tabs>
      <Box className="p-3">
        {tab === 'predictions' ? (
          <PredictionsTable modelId={modelId} timeZone={timeZone} />
        ) : (
          <AuditTable modelId={modelId} timeZone={timeZone} />
        )}
      </Box>
    </Paper>
  );
}
