import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { DailyReportDto, DailyReportPrefillDto } from '../../../../api/allocationTypes';
import type { allocationService } from '../../../../api/services/allocationService';
import { recordPath, recordRoutePattern } from '../../../../navigation/recordRoutes';
import { MACHINE, MACHINE_ID, ME_ID } from '../../../../test/jobFixtures';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { DailyReportDetailPage } from './DailyReportDetailPage';
import { DailyReportsPage } from './DailyReportsPage';
import { SubmitDailyReportDialog } from './SubmitDailyReportDialog';

const m = vi.hoisted(() => ({
  listReports: vi.fn<typeof allocationService.listReports>(),
  getReport: vi.fn<typeof allocationService.getReport>(),
  prefillReport: vi.fn<typeof allocationService.prefillReport>(),
  submitReport: vi.fn<typeof allocationService.submitReport>(),
  reviewReport: vi.fn<typeof allocationService.reviewReport>(),
}));
vi.mock('../../../../api/services/allocationService', () => ({ allocationService: m }));
vi.mock('../../../../api/services/jobService', () => ({
  jobService: { fieldMachines: vi.fn().mockResolvedValue([MACHINE]) },
}));

const OTHER = '44444444-4444-4444-8444-444444444444';
const R_ID = 'aaaaaaaa-0000-4000-8000-000000000001';
const OPENING = 'cccccccc-0000-4000-8000-000000000001';
const CLOSING = 'cccccccc-0000-4000-8000-000000000002';

const report = (o: Partial<DailyReportDto> = {}): DailyReportDto => ({
  id: R_ID,
  machine_id: MACHINE_ID,
  machine_code: 'EX-01',
  machine_name: 'Excavator',
  report_date: '2026-11-02',
  opening_ref: OPENING,
  opening_reading: '1000.00',
  closing_ref: CLOSING,
  closing_reading: '1010.00',
  total_hours: '10.00',
  billable_hours: '8.00',
  unbillable_hours: '1.00',
  difference_hours: '1.00',
  unbillable: [{ reason_id: 'r1', reason_name: 'Breakdown', hours: '1.00' }],
  allocations: [],
  evidence_attachment_ids: [],
  note: null,
  status: 'SUBMITTED',
  supersedes_id: null,
  is_duplicate: true,
  duplicate_of_id: 'aaaaaaaa-0000-4000-8000-000000000009',
  is_late: true,
  submitted_by: OTHER,
  submitted_by_name: 'Sam Supervisor',
  submitted_at: '2026-11-02T18:00:00Z',
  client_created_at: '2026-11-02T17:59:00Z',
  reviewed_by: null,
  reviewed_at: null,
  review_note: null,
  source: 'API',
  policy_version: 'EH:P1',
  ...o,
});

const prefill = (o: Partial<DailyReportPrefillDto> = {}): DailyReportPrefillDto => ({
  machine_id: MACHINE_ID,
  machine_code: 'EX-01',
  machine_name: 'Excavator',
  report_date: '2026-11-02',
  opening_ref: OPENING,
  opening_reading: '1000.00',
  opening_at: '2026-11-02T06:00:00Z',
  closing_ref: CLOSING,
  closing_reading: '1010.00',
  closing_at: '2026-11-02T18:00:00Z',
  total_hours: '10.00',
  customer_hours: '6.00',
  authorized_hours: '3.00',
  unexplained_hours: '1.00',
  allocations: [],
  existing_report_ids: [],
  ...o,
});

const renderDetail = (permissions: string[]) =>
  renderWithProviders(
    <Routes>
      <Route path={recordRoutePattern('DAILY_REPORT')} element={<DailyReportDetailPage />} />
    </Routes>,
    { tenantPermissions: permissions, route: recordPath('DAILY_REPORT', R_ID) },
  );

beforeEach(() => {
  vi.clearAllMocks();
});

describe('DailyReportsPage', () => {
  it('lists hours with the difference, late and duplicate chips', async () => {
    m.listReports.mockResolvedValue({ items: [report()], total: 1, page: 1, page_size: 20 });
    renderWithProviders(<DailyReportsPage />, { tenantPermissions: ['tenant.meter.read'] });
    expect(await screen.findByText('Late')).toBeInTheDocument();
    expect(screen.getByText('Duplicate')).toBeInTheDocument();
    expect(screen.getByText('1.00 h')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New daily report' })).not.toBeInTheDocument();
  });
});

describe('DailyReportDetailPage', () => {
  it('disables Review on your own report and explains why', async () => {
    m.getReport.mockResolvedValue(report({ submitted_by: ME_ID }));
    renderDetail(['tenant.meter.read', 'tenant.meter.review']);
    expect(await screen.findByRole('button', { name: 'Review' })).toBeDisabled();
    expect(screen.getByText(/Someone else must decide your own request/)).toBeInTheDocument();
  });

  it('records a return with its note', async () => {
    const user = userEvent.setup();
    m.getReport.mockResolvedValue(report());
    m.reviewReport.mockResolvedValue(report({ status: 'RETURNED' }));
    renderDetail(['tenant.meter.read', 'tenant.meter.review']);
    await user.click(await screen.findByRole('button', { name: 'Review' }));
    await user.click(await screen.findByRole('combobox', { name: /Outcome/ }));
    await user.click(await screen.findByRole('option', { name: 'Returned to the submitter' }));
    await user.type(screen.getByRole('textbox', { name: /Note/ }), 'Closing reading is unclear');
    await user.click(screen.getByRole('button', { name: 'Record review' }));
    await waitFor(() => {
      expect(m.reviewReport).toHaveBeenCalled();
    });
    expect(m.reviewReport.mock.calls[0]?.slice(0, 2)).toEqual([
      R_ID,
      { decision: 'RETURNED', note: 'Closing reading is unclear' },
    ]);
  });
});

describe('SubmitDailyReportDialog', () => {
  it('pre-fills from the day and submits the named readings as a replacement', async () => {
    const user = userEvent.setup();
    m.prefillReport.mockResolvedValue(prefill());
    m.submitReport.mockResolvedValue(report());
    const onSubmitted = vi.fn();
    const old = report({ status: 'RETURNED', unbillable: [] });
    renderWithProviders(
      <SubmitDailyReportDialog replaces={old} onClose={vi.fn()} onSubmitted={onSubmitted} />,
      { tenantPermissions: ['tenant.meter.capture'] },
    );
    expect(await screen.findByText('1010.00')).toBeInTheDocument();
    expect(m.prefillReport).toHaveBeenCalledWith(MACHINE_ID, '2026-11-02', expect.any(AbortSignal));
    await user.type(screen.getByRole('textbox', { name: /Billable hours/ }), '9');
    await user.click(screen.getByRole('button', { name: 'Submit report' }));
    await waitFor(() => {
      expect(onSubmitted).toHaveBeenCalled();
    });
    expect(m.submitReport.mock.calls[0]?.[0]).toMatchObject({
      machine_id: MACHINE_ID,
      report_date: '2026-11-02',
      opening_ref: OPENING,
      closing_ref: CLOSING,
      billable_hours: '9',
      supersedes_id: R_ID,
    });
  });

  it('warns about a repeat and refuses hours above the total', async () => {
    const user = userEvent.setup();
    m.prefillReport.mockResolvedValue(prefill({ existing_report_ids: ['x'] }));
    const old = report({ status: 'RETURNED', unbillable: [] });
    renderWithProviders(
      <SubmitDailyReportDialog replaces={old} onClose={vi.fn()} onSubmitted={vi.fn()} />,
      { tenantPermissions: ['tenant.meter.capture'] },
    );
    await screen.findByText('1010.00');
    expect(screen.queryByText(/flags this one as a duplicate/)).not.toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Billable hours/ }), '11');
    await user.click(screen.getByRole('button', { name: 'Submit report' }));
    expect(await screen.findByText(/are more than the day/)).toBeInTheDocument();
    expect(m.submitReport).not.toHaveBeenCalled();
  });
});
