import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type {
  DataExportDto,
  VerificationRunDto,
  VerificationRunSummaryDto,
  dataProtectionService,
} from '../../../api/services/dataProtectionService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { BalanceVerificationPage } from './BalanceVerificationPage';
import { DataExportPage } from './DataExportPage';

const m = vi.hoisted(() => ({
  listExports: vi.fn<typeof dataProtectionService.listExports>(),
  requestExport: vi.fn<typeof dataProtectionService.requestExport>(),
  downloadLink: vi.fn<typeof dataProtectionService.downloadLink>(),
  listRuns: vi.fn<typeof dataProtectionService.listRuns>(),
  getRun: vi.fn<typeof dataProtectionService.getRun>(),
  runNow: vi.fn<typeof dataProtectionService.runNow>(),
}));
vi.mock('../../../api/services/dataProtectionService', () => ({ dataProtectionService: m }));

function page<T>(items: T[]) {
  return { items, total: items.length, page: 1, page_size: 25 };
}

const exportRow: DataExportDto = {
  id: 'e1',
  format: 'CSV',
  status: 'COMPLETED',
  requested_by: 'u1',
  requested_at: '2026-11-08T08:00:00Z',
  started_at: '2026-11-08T08:00:10Z',
  finished_at: '2026-11-08T08:01:00Z',
  expires_at: '2026-11-15T08:01:00Z',
  sha256: 'abc',
  size_bytes: 1048576,
  table_count: 90,
  row_count: 1234,
  evidence_count: 7,
  error_code: null,
};

const summary: VerificationRunSummaryDto = {
  id: 'r1',
  tenant_id: 't1',
  trigger: 'MANUAL',
  requested_by: 'u1',
  started_at: '2026-11-08T08:00:00Z',
  finished_at: '2026-11-08T08:00:02Z',
  outcome: 'MISMATCHES',
  checked_count: 12,
  mismatch_count: 1,
  summary: [{ check: 'CUSTOMER_HOURS_LOT', checked: 10, mismatches: 1 }],
};

const detail: VerificationRunDto = {
  ...summary,
  findings: [
    {
      check: 'CUSTOMER_HOURS_LOT',
      subject_type: 'hours_purchase',
      subject_id: 'p1',
      label: 'HP-2026-00001 on EXC-1',
      currency: null,
      ledger_value: '7.50',
      stored_value: '999.00',
      difference: '991.50',
      source: 'adjustment new_value',
      details: {},
    },
  ],
  findings_truncated: false,
};

const me = (tenantPermissions: string[]) => ({ tenantPermissions });

describe('Data export', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    m.listExports.mockResolvedValue(page([exportRow]));
  });

  it('lists exports and requests a new one', async () => {
    m.requestExport.mockResolvedValue({ ...exportRow, id: 'e2', status: 'QUEUED' });
    renderWithProviders(<DataExportPage />, me([P.tenantDataExport]));
    expect(await screen.findByText('1234')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Request export' }));
    await waitFor(() => {
      expect(m.requestExport).toHaveBeenCalledWith('CSV');
    });
  });

  it('asks the server for a download link', async () => {
    m.downloadLink.mockResolvedValue({ url: 'about:blank', expires_in_seconds: 300 });
    renderWithProviders(<DataExportPage />, me([P.tenantDataExport]));
    await userEvent.click(await screen.findByRole('button', { name: 'Download' }));
    await waitFor(() => {
      expect(m.downloadLink).toHaveBeenCalledWith('e1');
    });
  });
});

describe('Data export on a read-only subscription', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    m.listExports.mockResolvedValue(page([exportRow]));
  });

  it('still offers the export request and the download', async () => {
    m.requestExport.mockResolvedValue({ ...exportRow, id: 'e2', status: 'QUEUED' });
    m.downloadLink.mockResolvedValue({ url: 'about:blank', expires_in_seconds: 300 });
    renderWithProviders(<DataExportPage />, {
      tenantPermissions: [P.tenantDataExport],
      accessState: 'READ_ONLY',
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Download' }));
    await userEvent.click(screen.getByRole('button', { name: 'Request export' }));
    await waitFor(() => {
      expect(m.downloadLink).toHaveBeenCalledWith('e1');
      expect(m.requestExport).toHaveBeenCalledWith('CSV');
    });
  });
});

describe('Balance verification', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    m.listRuns.mockResolvedValue(page([summary]));
    m.getRun.mockResolvedValue(detail);
  });

  it('runs a verification when permitted', async () => {
    m.runNow.mockResolvedValue(detail);
    renderWithProviders(
      <BalanceVerificationPage />,
      me([P.tenantBalanceRead, P.tenantBalanceVerify]),
    );
    await userEvent.click(await screen.findByRole('button', { name: 'Verify now' }));
    await waitFor(() => {
      expect(m.runNow).toHaveBeenCalled();
    });
  });

  it('names the petty cash fund check in plain words', async () => {
    m.getRun.mockResolvedValue({
      ...detail,
      findings: [
        {
          check: 'PETTY_CASH_FUND',
          subject_type: 'petty_cash_fund',
          subject_id: 'f1',
          label: 'PC-01 Office box',
          currency: 'TZS',
          ledger_value: '300000.0000',
          stored_value: '290000.0000',
          difference: '10000.0000',
          source: 'count PC-000004 expected cash',
          details: {},
        },
      ],
    });
    renderWithProviders(<BalanceVerificationPage />, me([P.tenantBalanceRead]));
    await userEvent.click(await screen.findByRole('button', { name: 'Show findings' }));
    expect(await screen.findByText('Petty cash per fund')).toBeInTheDocument();
    expect(screen.queryByText('PETTY_CASH_FUND')).toBeNull();
  });

  it('hides the action without the permission and shows recorded results', async () => {
    renderWithProviders(<BalanceVerificationPage />, me([P.tenantBalanceRead]));
    expect(await screen.findByText('Mismatches')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Verify now' })).toBeNull();
  });
});
