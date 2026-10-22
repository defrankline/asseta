import { Alert, Box, Typography } from '@mui/material';
import type {
  MlApprovalDto,
  MlEvaluationDto,
  MlManifestSummaryDto,
  MlModelVersionDto,
} from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { DetailSection } from '../../../components/lifecycle/EntityDetailsLayout';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import {
  ACTION_LABELS,
  ALGORITHM_LABELS,
  MODEL_STATUS_LABELS,
  metricText,
  shortHash,
} from './modelDisplay';

type Json = Record<string, unknown>;

const asRecord = (value: unknown): Json =>
  typeof value === 'object' && value !== null && !Array.isArray(value) ? (value as Json) : {};

/** Metric names (backend `ScorerMetrics.as_dict`) in plain words. */
const METRIC_LABELS: Readonly<Record<string, string>> = {
  recall_at_k: 'Recall at k (injected unusual weeks found)',
  precision_at_k: 'Precision at k',
  k: 'k (weeks reviewed)',
  n_injected: 'Injected test weeks',
  calibrated: 'Calibrated',
  alert_rate: 'Alert rate on normal weeks',
  recall_fold_std: 'Recall spread across time folds',
  recall_fold_mean: 'Mean recall across time folds',
};

interface MetricRow {
  key: string;
  baseline: unknown;
  candidate: unknown;
}

/** Summary of the version: algorithm, data window, artefacts. */
export function ModelSummarySection({ m, timeZone }: { m: MlModelVersionDto; timeZone: string }) {
  return (
    <DetailSection title="Summary">
      <KeyValueGrid
        columns={3}
        items={[
          { label: 'Tenant', value: m.tenant_name ?? m.tenant_id },
          { label: 'Algorithm', value: ALGORITHM_LABELS[m.algorithm] },
          { label: 'Baseline', value: ALGORITHM_LABELS[m.baseline_algorithm] },
          {
            label: 'Training window',
            value: `${formatInstantIn(m.training_window_start, timeZone)} – ${formatInstantIn(
              m.training_window_end,
              timeZone,
            )}`,
          },
          { label: 'Feature set hash', value: shortHash(m.feature_set_hash) },
          { label: 'Artefact SHA-256', value: shortHash(m.artifact_sha256) },
          { label: 'MLflow run', value: m.mlflow_run_id ?? '—' },
          { label: 'Status since', value: formatInstantIn(m.status_changed_at, timeZone) },
          { label: 'Deployed', value: formatInstantIn(m.deployed_at, timeZone) },
          ...(m.tracking_note !== null ? [{ label: 'Tracking note', value: m.tracking_note }] : []),
        ]}
      />
    </DetailSection>
  );
}

/** Candidate vs statistical baseline, promotion criteria and the pass / fail reasons. */
export function EvaluationSection({
  evaluation,
  timeZone,
}: {
  evaluation: MlEvaluationDto | null;
  timeZone: string;
}) {
  if (evaluation === null) {
    return (
      <DetailSection title="Evaluation vs baseline">
        <Alert severity="info">No evaluation recorded yet. Approval and deployment need one.</Alert>
      </DetailSection>
    );
  }
  const baseline = asRecord(evaluation.metrics.baseline);
  const candidate = asRecord(evaluation.metrics.candidate);
  const keys = [...new Set([...Object.keys(candidate), ...Object.keys(baseline)])];
  const rows: MetricRow[] = keys.map((key) => ({
    key,
    baseline: baseline[key],
    candidate: candidate[key],
  }));
  const calibrated = candidate.calibrated === 1 || candidate.calibrated === true;
  const columns: DataColumn<MetricRow>[] = [
    { id: 'metric', header: 'Metric', render: (r) => METRIC_LABELS[r.key] ?? humanize(r.key) },
    { id: 'baseline', header: 'Baseline', align: 'right', render: (r) => metricText(r.baseline) },
    {
      id: 'candidate',
      header: 'Candidate',
      align: 'right',
      render: (r) => metricText(r.candidate),
    },
  ];
  const promotion = asRecord(evaluation.criteria.promotion);
  const sufficiency = asRecord(evaluation.criteria.sufficiency);
  const criteria = [...Object.entries(promotion), ...Object.entries(sufficiency)].map(([k, v]) => ({
    label: humanize(k),
    value: metricText(v),
  }));
  return (
    <DetailSection
      title="Evaluation vs baseline"
      actions={
        <Box className="flex gap-2">
          <StatusChip
            status={evaluation.passed ? 'PASSED' : 'FAILED'}
            tones={{ PASSED: 'success', FAILED: 'warning' }}
            label={evaluation.passed ? 'Passed' : 'Not passed'}
          />
          <StatusChip
            status={calibrated ? 'CAL' : 'UNCAL'}
            tones={{ CAL: 'info', UNCAL: 'default' }}
            label={calibrated ? 'Calibrated' : 'Not calibrated'}
          />
        </Box>
      }
    >
      <Box className="flex flex-col gap-3">
        <Typography variant="body2" color="text.secondary">
          Evaluated {formatInstantIn(evaluation.evaluated_at, timeZone)}. Scores are model-specific
          rankings, not probabilities
          {calibrated ? '; calibrated scores are percentiles against held-out weeks.' : '.'}
        </Typography>
        {evaluation.reasons.length > 0 && (
          <Box component="ul" className="m-0 pl-5" aria-label="Evaluation reasons">
            {evaluation.reasons.map((r) => (
              <li key={r}>
                <Typography variant="body2">{r}</Typography>
              </li>
            ))}
          </Box>
        )}
        {evaluation.metrics.recall_lift !== undefined && (
          <Typography variant="body2">
            Recall lift over baseline: {metricText(evaluation.metrics.recall_lift)}
          </Typography>
        )}
        <StaticTable
          ariaLabel="Evaluation metrics"
          columns={columns}
          rows={rows}
          getRowId={(r) => r.key}
        />
        {criteria.length > 0 && (
          <>
            <Typography variant="subtitle2" component="h3">
              Promotion and sufficiency criteria
            </Typography>
            <KeyValueGrid columns={3} items={criteria} />
          </>
        )}
      </Box>
    </DetailSection>
  );
}

/** Training-set manifest: rows per split, time boundaries and hashes. */
export function ManifestSection({ manifest }: { manifest: MlManifestSummaryDto }) {
  return (
    <DetailSection title="Training data manifest">
      <KeyValueGrid
        columns={3}
        items={[
          ...Object.entries(manifest.rows).map(([split, n]) => ({
            label: `${humanize(split)} rows`,
            value: String(n),
          })),
          { label: 'Machines', value: String(manifest.entities) },
          { label: 'Train split ends', value: manifest.train_end ?? '—' },
          { label: 'Validation split ends', value: manifest.validation_end ?? '—' },
          {
            label: 'Purged rows',
            value: manifest.purged_rows === null ? '—' : String(manifest.purged_rows),
          },
          { label: 'Content hash', value: shortHash(manifest.content_hash) },
          { label: 'Features', value: manifest.feature_codes.join(', ') || '—' },
        ]}
      />
    </DetailSection>
  );
}

/** Append-only lifecycle log (train, approve, deploy, rollback, …) with reasons. */
export function ApprovalsSection({
  approvals,
  timeZone,
}: {
  approvals: readonly MlApprovalDto[];
  timeZone: string;
}) {
  const columns: DataColumn<MlApprovalDto>[] = [
    { id: 'when', header: 'When', render: (a) => formatInstantIn(a.decided_at, timeZone) },
    { id: 'action', header: 'Action', render: (a) => ACTION_LABELS[a.action] },
    {
      id: 'change',
      header: 'Status change',
      render: (a) =>
        `${a.from_status === null ? '—' : MODEL_STATUS_LABELS[a.from_status]} → ${
          MODEL_STATUS_LABELS[a.to_status]
        }`,
    },
    { id: 'reason', header: 'Reason', render: (a) => a.reason },
    {
      id: 'by',
      header: 'Decided by',
      render: (a) => a.decided_by_name ?? (a.decided_by === null ? 'System' : a.decided_by),
    },
  ];
  return (
    <DetailSection title="Lifecycle history">
      {approvals.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No decisions recorded yet.
        </Typography>
      ) : (
        <StaticTable
          ariaLabel="Lifecycle history"
          columns={columns}
          rows={approvals}
          getRowId={(a) => a.id}
        />
      )}
    </DetailSection>
  );
}
