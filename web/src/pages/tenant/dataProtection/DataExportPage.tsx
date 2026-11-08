import Download from '@mui/icons-material/Download';
import { Alert, Button, MenuItem, Stack, TextField } from '@mui/material';
import { useCallback, useEffect, useState } from 'react';
import { toApiError } from '../../../api/ApiError';
import {
  dataProtectionService,
  type DataExportDto,
  type ExportFormat,
} from '../../../api/services/dataProtectionService';
import { StatusChip, type StatusTone } from '../../../components/display/StatusChip';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';

const TONES: Readonly<Record<string, StatusTone>> = {
  QUEUED: 'info',
  RUNNING: 'info',
  COMPLETED: 'success',
  FAILED: 'error',
  EXPIRED: 'default',
};
const POLL_MS = 15_000;

const size = (bytes: number | null) =>
  bytes === null ? '—' : `${(bytes / (1024 * 1024)).toFixed(bytes < 1024 * 1024 ? 2 : 1)} MB`;

/**
 * Full company data export: every ledger and business record in one ZIP, built in the background,
 * downloaded through a short-lived link. Evidence files are listed in the ZIP's manifest with the
 * address to fetch each one; every request and download is audited.
 */
export function DataExportPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const [format, setFormat] = useState<ExportFormat>('CSV');
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  const [requesting, setRequesting] = useState(false);

  useEffect(() => {
    const timer = window.setInterval(reload, POLL_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [reload]);

  const fetchPage = useCallback<FetchPage<DataExportDto>>(
    (query, signal) => dataProtectionService.listExports(query, signal),
    [],
  );

  const request = () => {
    setRequesting(true);
    dataProtectionService
      .requestExport(format)
      .then(() => {
        notify.success('Export requested. It is being prepared.');
        reload();
      })
      .catch((e: unknown) => {
        notify.error(
          toApiError(e).code === 'EXPORT_IN_PROGRESS'
            ? 'An export is already being prepared.'
            : 'The export could not be requested.',
        );
      })
      .finally(() => {
        setRequesting(false);
      });
  };

  const download = (row: DataExportDto) => {
    dataProtectionService
      .downloadLink(row.id)
      .then((link) => {
        window.location.assign(link.url);
      })
      .catch(() => {
        notify.error('The download link could not be created.');
      });
  };

  const columns: DataColumn<DataExportDto>[] = [
    { id: 'at', header: 'Requested', render: (r) => formatInstantIn(r.requested_at, timeZone) },
    { id: 'format', header: 'Format', render: (r) => r.format },
    {
      id: 'status',
      header: 'Status',
      render: (r) => <StatusChip status={r.status} tones={TONES} />,
    },
    { id: 'rows', header: 'Records', align: 'right', render: (r) => r.row_count ?? '—' },
    {
      id: 'files',
      header: 'Evidence files',
      align: 'right',
      render: (r) => r.evidence_count ?? '—',
    },
    { id: 'size', header: 'Size', align: 'right', render: (r) => size(r.size_bytes) },
    {
      id: 'until',
      header: 'Available until',
      render: (r) => (r.expires_at ? formatInstantIn(r.expires_at, timeZone) : '—'),
    },
    {
      id: 'actions',
      header: '',
      render: (r) =>
        r.status === 'COMPLETED' ? (
          <Button
            size="small"
            startIcon={<Download />}
            onClick={() => {
              download(r);
            }}
          >
            Download
          </Button>
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        title="Data export"
        subtitle="Download every ledger and business record of your company"
        actions={
          <Stack direction="row" className="gap-2">
            <TextField
              select
              size="small"
              label="Format"
              value={format}
              onChange={(e) => {
                setFormat(e.target.value as ExportFormat);
              }}
            >
              <MenuItem value="CSV">CSV</MenuItem>
              <MenuItem value="JSON">JSON</MenuItem>
            </TextField>
            <Button variant="contained" onClick={request} disabled={requesting}>
              Request export
            </Button>
          </Stack>
        }
      />
      <Alert severity="info" className="mb-4">
        The export is prepared in the background and appears here when it is ready. Evidence files
        (photos, receipts, signatures) are listed in the ZIP with the address to fetch each one.
        Keep the file on encrypted storage: it holds your complete records.
      </Alert>
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(r) => r.id}
        reloadKey={reloadKey}
        emptyTitle="No exports yet"
        emptyDescription="Request an export to download your company's data."
      />
    </>
  );
}
