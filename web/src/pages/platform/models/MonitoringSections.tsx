import { Alert, Box, Typography } from '@mui/material';
import { useCallback } from 'react';
import { platformMlService } from '../../../api/services/platformMlService';
import type { MlDriftDto, MlDriftFeatureDto, MlMonitoringDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { DetailSection } from '../../../components/lifecycle/EntityDetailsLayout';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import { DECISION_LABELS, DRIFT_LABELS, DRIFT_TONES, metricText } from './modelDisplay';

function DriftChip({ level }: { level: string }) {
  return (
    <StatusChip status={level} tones={DRIFT_TONES} label={DRIFT_LABELS[level] ?? humanize(level)} />
  );
}

/** Latest PSI per feature (training vs recent four weeks) and the drift history. */
export function DriftSection({
  modelId,
  drift,
  timeZone,
}: {
  modelId: string;
  drift: MlDriftDto | null;
  timeZone: string;
}) {
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      platformMlService.listDrift(modelId, { page: q.page, page_size: q.page_size }, signal),
    [modelId],
  );
  const featureColumns: DataColumn<MlDriftFeatureDto>[] = [
    { id: 'feature', header: 'Feature', render: (f) => f.feature },
    { id: 'psi', header: 'PSI', align: 'right', render: (f) => metricText(f.psi) },
    { id: 'level', header: 'Level', render: (f) => <DriftChip level={f.level} /> },
    { id: 'train', header: 'Training rows', align: 'right', render: (f) => f.n_expected },
    { id: 'recent', header: 'Recent rows', align: 'right', render: (f) => f.n_actual },
  ];
  const historyColumns: DataColumn<MlDriftDto>[] = [
    { id: 'at', header: 'Checked', render: (d) => formatInstantIn(d.computed_at, timeZone) },
    { id: 'level', header: 'Level', render: (d) => <DriftChip level={d.level} /> },
    { id: 'summary', header: 'Summary', render: (d) => d.summary },
    {
      id: 'rows',
      header: 'Rows (train / recent)',
      align: 'right',
      render: (d) => `${String(d.n_train)} / ${String(d.n_recent)}`,
    },
  ];
  return (
    <DetailSection
      title="Drift"
      {...(drift !== null ? { actions: <DriftChip level={drift.level} /> } : {})}
    >
      <Box className="flex flex-col gap-3">
        {drift === null ? (
          <Alert severity="info">No drift check yet. Checks run daily for deployed versions.</Alert>
        ) : (
          <>
            <Typography variant="body2">{drift.summary}</Typography>
            <Typography variant="caption" color="text.secondary">
              Training {formatInstantIn(drift.train_start, timeZone)} –{' '}
              {formatInstantIn(drift.train_end, timeZone)} vs recent{' '}
              {formatInstantIn(drift.recent_start, timeZone)} –{' '}
              {formatInstantIn(drift.recent_end, timeZone)}. PSI below 0.1 is stable, 0.1–0.25 worth
              watching, 0.25 or more drift.
            </Typography>
            <StaticTable
              ariaLabel="Drift per feature"
              columns={featureColumns}
              rows={drift.features}
              getRowId={(f) => f.feature}
            />
          </>
        )}
        <Typography variant="subtitle2" component="h3">
          Drift history
        </Typography>
        <ServerDataTable<MlDriftDto>
          columns={historyColumns}
          fetchPage={fetchPage}
          getRowId={(d) => d.id}
          searchable={false}
          initialPageSize={10}
          emptyTitle="No drift checks recorded"
        />
      </Box>
    </DetailSection>
  );
}

const countsText = (
  counts: Readonly<Record<string, number>>,
  labels?: Readonly<Record<string, string>>,
) => {
  const entries = Object.entries(counts);
  if (entries.length === 0) return 'None yet';
  return entries.map(([k, n]) => `${labels?.[k] ?? humanize(k)}: ${String(n)}`).join(' · ');
};

/** Inference latency and volume for this version. */
export function MonitoringSection({
  monitoring,
  timeZone,
}: {
  monitoring: MlMonitoringDto | null;
  timeZone: string;
}) {
  return (
    <DetailSection title="Monitoring">
      {monitoring === null ? (
        <Alert severity="info">No inference has run for this version.</Alert>
      ) : (
        <Box className="flex flex-col gap-3">
          {monitoring.last_error !== null && (
            <Alert severity="warning">Last run failed: {monitoring.last_error}</Alert>
          )}
          <KeyValueGrid
            columns={3}
            items={[
              {
                label: 'Latency p50',
                value:
                  monitoring.latency_p50_ms === null
                    ? '—'
                    : `${metricText(monitoring.latency_p50_ms)} ms`,
              },
              {
                label: 'Latency p95',
                value:
                  monitoring.latency_p95_ms === null
                    ? '—'
                    : `${metricText(monitoring.latency_p95_ms)} ms`,
              },
              {
                label: 'Last inference',
                value: formatInstantIn(monitoring.last_inference_at, timeZone),
              },
              { label: 'Runs by outcome', value: countsText(monitoring.runs_by_outcome) },
              {
                label: 'Predictions by decision',
                value: countsText(monitoring.predictions_by_state, DECISION_LABELS),
              },
            ]}
          />
        </Box>
      )}
    </DetailSection>
  );
}
