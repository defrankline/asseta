import { Alert, Box, Button, Link, Typography } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { platformMlService } from '../../../api/services/platformMlService';
import type { MlReadinessDto, TenantDto } from '../../../api/types';
import { AsyncAutocomplete } from '../../../components/data/AsyncAutocomplete';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { modelDetailPath } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import { searchTenants, tenantLabel } from '../shared/platformLookups';
import {
  MODEL_STATUS_LABELS,
  READINESS_LABELS,
  READINESS_OPTIONS,
  READINESS_TONES,
} from './modelDisplay';
import { RunDialog, type RunKind, type RunResult } from './RunDialogs';

type Running = { kind: RunKind; tenant: { id: string; name: string } | null } | null;

function RunSummary({ run, onClose }: { run: RunResult; onClose: () => void }) {
  if (run.kind === 'snapshots') {
    const r = run.result;
    return (
      <Alert severity="success" onClose={onClose}>
        Snapshots refreshed for {run.tenantName}: {r.written} written across {r.week_ends.length}{' '}
        weeks and {r.machines} machines ({r.skipped_existing} already present, {r.skipped_future}{' '}
        future weeks skipped).
      </Alert>
    );
  }
  const { readiness, model } = run.result;
  if (model === null) {
    return (
      <Alert severity="info" onClose={onClose}>
        No new version for {run.tenantName}: {READINESS_LABELS[readiness.status].toLowerCase()}.{' '}
        {readiness.reasons.join(' ')}
      </Alert>
    );
  }
  return (
    <Alert severity="success" onClose={onClose}>
      Trained {model.name} version {model.version} for {run.tenantName} (
      {MODEL_STATUS_LABELS[model.status]}).{' '}
      <Link component={RouterLink} to={modelDetailPath(model.id)}>
        Open the new version
      </Link>
    </Alert>
  );
}

/** Latest readiness per tenant with the snapshot / training triggers (platform.ml.manage). */
export function ReadinessSection({
  timeZone,
  canManage,
  onTrained,
}: {
  timeZone: string;
  canManage: boolean;
  onTrained: () => void;
}) {
  const [status, setStatus] = useState('');
  const [tenant, setTenant] = useState<TenantDto | null>(null);
  const [running, setRunning] = useState<Running>(null);
  const [lastRun, setLastRun] = useState<RunResult | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const filters = useMemo(
    () => ({ status: status || undefined, tenant_id: tenant?.id }),
    [status, tenant],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      platformMlService.listReadiness(
        { page: q.page, page_size: q.page_size, filters: q.filters },
        signal,
      ),
    [],
  );
  const runFor = (kind: RunKind, r: MlReadinessDto) => () => {
    setRunning({ kind, tenant: { id: r.tenant_id, name: r.tenant_name ?? r.tenant_id } });
  };
  const columns: DataColumn<MlReadinessDto>[] = [
    { id: 'tenant', header: 'Tenant', render: (r) => r.tenant_name ?? r.tenant_id },
    { id: 'model', header: 'Model', render: (r) => r.model_name },
    {
      id: 'status',
      header: 'Readiness',
      render: (r) => (
        <StatusChip status={r.status} tones={READINESS_TONES} label={READINESS_LABELS[r.status]} />
      ),
    },
    {
      id: 'reasons',
      header: 'What is missing',
      render: (r) => (r.reasons.length === 0 ? '—' : r.reasons.join(' ')),
    },
    { id: 'rows', header: 'Snapshot rows', align: 'right', render: (r) => r.snapshot_rows },
    { id: 'at', header: 'Assessed', render: (r) => formatInstantIn(r.computed_at, timeZone) },
    ...(canManage
      ? [
          {
            id: 'actions',
            header: 'Run',
            render: (r: MlReadinessDto) => (
              <Box className="flex flex-wrap gap-1">
                <Button size="small" onClick={runFor('snapshots', r)}>
                  Refresh snapshots
                </Button>
                <Button size="small" onClick={runFor('train', r)}>
                  Train now
                </Button>
              </Box>
            ),
          },
        ]
      : []),
  ];
  return (
    <Box component="section" aria-label="Readiness per tenant" className="flex flex-col gap-2">
      <Box className="flex flex-wrap items-center justify-between gap-2">
        <Typography variant="h6" component="h2">
          Readiness per tenant
        </Typography>
        {canManage && (
          <Box className="flex gap-2">
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                setRunning({ kind: 'snapshots', tenant: null });
              }}
            >
              Refresh snapshots…
            </Button>
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                setRunning({ kind: 'train', tenant: null });
              }}
            >
              Train now…
            </Button>
          </Box>
        )}
      </Box>
      {lastRun !== null && (
        <RunSummary
          run={lastRun}
          onClose={() => {
            setLastRun(null);
          }}
        />
      )}
      <ServerDataTable<MlReadinessDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(r) => r.id}
        filters={filters}
        searchable={false}
        reloadKey={reloadKey}
        emptyTitle="No readiness assessed yet"
        emptyDescription="Readiness is recorded when snapshots or training run for a tenant."
        toolbar={
          <>
            <Box className="min-w-56">
              <AsyncAutocomplete<TenantDto>
                label="Tenant"
                value={tenant}
                onChange={setTenant}
                fetchOptions={searchTenants}
                getOptionLabel={tenantLabel}
                isOptionEqualToValue={(a, b) => a.id === b.id}
              />
            </Box>
            <StaticSelectFilter
              label="Readiness"
              value={status}
              options={READINESS_OPTIONS}
              onChange={setStatus}
              allLabel="Any readiness"
            />
          </>
        }
      />
      {running !== null && (
        <RunDialog
          kind={running.kind}
          tenant={running.tenant}
          onClose={() => {
            setRunning(null);
          }}
          onDone={(result) => {
            setLastRun(result);
            setReloadKey((k) => k + 1);
            if (result.kind === 'train' && result.result.model !== null) onTrained();
          }}
        />
      )}
    </Box>
  );
}
