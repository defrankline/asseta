import Refresh from '@mui/icons-material/Refresh';
import {
  Button,
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import { useCallback, useEffect, useState } from 'react';
import { isCancelled, toApiError, type ApiError } from '../api/ApiError';
import { healthService } from '../api/services/healthService';
import type { HealthReadyResponse } from '../api/types';
import { EmptyState } from '../components/feedback/EmptyState';
import { ErrorState } from '../components/feedback/ErrorState';
import { LoadingState } from '../components/feedback/LoadingState';
import { PageHeader } from '../components/feedback/PageHeader';

function statusColor(status: string): 'success' | 'warning' | 'error' | 'default' {
  if (status === 'ok') return 'success';
  if (status === 'degraded') return 'warning';
  if (status === 'error' || status === 'down' || status === 'fail') return 'error';
  return 'default';
}

interface ProbeResult {
  tick: number;
  data: HealthReadyResponse | null;
  error: ApiError | null;
  checkedAt: Date | null;
}

/** Live readiness of the API and its dependencies (GET /health/ready). */
export function SystemStatusPage() {
  const [tick, setTick] = useState(0);
  const [result, setResult] = useState<ProbeResult>({
    tick: -1,
    data: null,
    error: null,
    checkedAt: null,
  });

  useEffect(() => {
    const controller = new AbortController();
    healthService
      .getReady(controller.signal)
      .then((data) => {
        setResult({ tick, data, error: null, checkedAt: new Date() });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || isCancelled(err)) return;
        setResult((r) => ({ ...r, tick, error: toApiError(err) }));
      });
    return () => {
      controller.abort();
    };
  }, [tick]);

  const loading = result.tick !== tick;
  const { data, error, checkedAt } = result;
  const refresh = useCallback(() => {
    setTick((t) => t + 1);
  }, []);
  const checks = Object.entries(data?.checks ?? {});

  return (
    <>
      <PageHeader
        title="System status"
        subtitle={
          checkedAt !== null
            ? `Last checked ${checkedAt.toLocaleString()}`
            : 'API readiness and dependencies'
        }
        actions={
          <Button startIcon={<Refresh />} onClick={refresh} loading={loading} variant="outlined">
            Refresh
          </Button>
        }
      />
      {error !== null && (
        <ErrorState error={error} title="Readiness check failed" onRetry={refresh} />
      )}
      {error === null && data === null && <LoadingState label="Checking readiness" />}
      {error === null && data !== null && (
        <Paper variant="outlined" className="p-4">
          <div className="mb-4 flex items-center gap-2">
            <span className="font-semibold">Overall</span>
            <Chip label={data.status} color={statusColor(data.status)} size="small" />
          </div>
          {checks.length === 0 ? (
            <EmptyState title="No dependency checks reported" />
          ) : (
            <TableContainer>
              <Table size="small" aria-label="Dependency checks">
                <TableHead>
                  <TableRow>
                    <TableCell>Check</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Detail</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {checks.map(([name, check]) => (
                    <TableRow key={name}>
                      <TableCell className="font-mono">{name}</TableCell>
                      <TableCell>
                        <Chip label={check.status} color={statusColor(check.status)} size="small" />
                      </TableCell>
                      <TableCell>{check.detail ?? '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>
      )}
    </>
  );
}
