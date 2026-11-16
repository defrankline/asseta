import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type {
  machineReportReasonService,
  machineReportService,
} from '../../../api/services/machineReportService';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { ROUTES } from '../../../navigation/routes';
import { notificationTargetPath } from '../../../notifications/center/display';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { FieldMachineReportPage } from './FieldMachineReportPage';
import { MachineReportDetailPage } from './MachineReportDetailPage';
import { MachineReportReasonsPage } from './MachineReportReasonsPage';
import { CONTEXT, REPORT, STATUS } from './machineReportFixtures';

const ME = '33333333-3333-4333-8333-333333333333';

const m = vi.hoisted(() => ({
  list: vi.fn<typeof machineReportService.list>(),
  get: vi.fn<typeof machineReportService.get>(),
  submit: vi.fn<typeof machineReportService.submit>(),
  approve: vi.fn<typeof machineReportService.approve>(),
  reject: vi.fn<typeof machineReportService.reject>(),
  status: vi.fn<typeof machineReportService.status>(),
  context: vi.fn<typeof machineReportService.context>(),
  availableHours: vi.fn<typeof machineReportService.availableHours>(),
  reasons: vi.fn<typeof machineReportReasonService.list>(),
  createReason: vi.fn<typeof machineReportReasonService.create>(),
  gps: vi.fn(),
}));
vi.mock('../../../api/services/machineReportService', () => ({
  machineReportService: {
    list: m.list,
    get: m.get,
    submit: m.submit,
    approve: m.approve,
    reject: m.reject,
    status: m.status,
    context: m.context,
    availableHours: m.availableHours,
  },
  machineReportReasonService: {
    list: m.reasons,
    create: m.createReason,
    update: vi.fn(),
    deactivate: vi.fn(),
    reactivate: vi.fn(),
  },
}));
vi.mock('../../../utils/geolocation', () => ({ attemptGpsFix: m.gps }));
// Plain inputs stand in for the async pickers (their own tests cover them).
vi.mock('../../../components/forms/FormikAsyncIdAutocomplete', () => ({
  FormikAsyncIdAutocomplete: ({ name, label }: { name: string; label: string }) => (
    <FormikTextField name={name} label={label} />
  ),
}));
vi.mock('../shared/financePickers', () => ({
  MachineFilter: () => null,
  CustomerFilter: () => null,
}));

const SUBMIT = 'tenant.machine_report.submit';
const READ = 'tenant.machine_report.read';
const APPROVE = 'tenant.machine_report.approve';

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });

beforeEach(() => {
  m.gps.mockReset().mockResolvedValue({ status: 'FIX', latitude: -6.8, longitude: 39.28 });
  m.list.mockReset().mockResolvedValue(page([REPORT]));
  m.get.mockReset().mockResolvedValue(REPORT);
  m.submit.mockReset().mockResolvedValue(REPORT);
  m.approve.mockReset().mockResolvedValue({ ...REPORT, status: 'APPROVED' });
  m.reject.mockReset().mockResolvedValue({ ...REPORT, status: 'REJECTED' });
  m.status.mockReset().mockResolvedValue([STATUS]);
  m.context.mockReset().mockResolvedValue(CONTEXT);
  m.availableHours.mockReset().mockResolvedValue(CONTEXT.customers);
  m.reasons.mockReset().mockResolvedValue(CONTEXT.reasons);
  m.createReason.mockReset().mockResolvedValue(CONTEXT.reasons[0] as never);
});

describe('Field work › Machine report', () => {
  it('lists my machines with their report state and actions', async () => {
    m.status.mockResolvedValue([
      STATUS,
      {
        ...STATUS,
        machine_id: 'm2',
        machine_code: 'WL-01',
        pending_report_id: 'mr1',
        pending_report_number: 'MR-2026-00001',
      },
      { ...STATUS, machine_id: 'm3', machine_code: 'DZ-01', rejected_report_id: 'mr0' },
    ]);
    renderWithProviders(<FieldMachineReportPage />, { tenantPermissions: [SUBMIT, READ] });
    const table = await screen.findByRole('table', { name: 'My machines' });
    expect(within(table).getByText('Ready for a report')).toBeInTheDocument();
    expect(within(table).getByText('Waiting for a decision (MR-2026-00001)')).toBeInTheDocument();
    expect(within(table).getByText('Rejected: correct it')).toBeInTheDocument();
    expect(within(table).getByRole('button', { name: 'New report' })).toBeInTheDocument();
    expect(within(table).getByRole('button', { name: 'Correct report' })).toBeInTheDocument();
    expect(within(table).getByRole('button', { name: 'View' })).toBeInTheDocument();
    expect(m.list.mock.calls[0]?.[0].filters).toMatchObject({ mine: 'true' });
  });

  it('takes a reading, splits the hours until they match, and submits', async () => {
    const user = userEvent.setup();
    renderWithProviders(<FieldMachineReportPage />, { tenantPermissions: [SUBMIT, READ] });
    await user.click(await screen.findByRole('button', { name: 'New report' }));
    expect(await screen.findByText(/1,210 h · .* · last approved report/)).toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: /Capture mode/ }));
    await user.click(screen.getByRole('option', { name: /Manual/ }));
    await user.type(screen.getByRole('textbox', { name: /Meter reading/ }), '1510');
    expect(screen.getByText('Hours to account for: 300 h')).toBeInTheDocument();
    await waitFor(() => {
      expect(m.gps).toHaveBeenCalled();
    });
    await user.click(screen.getByRole('button', { name: 'Next' }));

    await user.click(await screen.findByRole('button', { name: 'Add customer' }));
    await user.type(screen.getByRole('textbox', { name: /^Customer/ }), 'c1');
    const hours = () => screen.getAllByRole('textbox', { name: /^Hours/ });
    expect(hours()[0]).toHaveValue('300');
    await user.clear(hours()[0] as HTMLElement);
    await user.type(hours()[0] as HTMLElement, '120');
    expect(screen.getByText('180 h still to account for')).toBeInTheDocument();
    expect(screen.getByText('Available 140 h · after this 20 h')).toBeInTheDocument();
    // Submit stays out of reach until the hours add up.
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.queryByRole('button', { name: 'Submit for approval' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Add non-productive' }));
    expect(hours()[1]).toHaveValue('180');
    await user.type(screen.getByRole('textbox', { name: /^Reason/ }), 'r1');
    await user.type(screen.getByRole('textbox', { name: /What happened/ }), 'Hydraulic hose');
    expect(screen.getByText('Every hour is accounted for.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText(/Total 300 h · matches the meter/)).toBeInTheDocument();
    expect(screen.getByText('Productive · 120 h')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Submit for approval' }));
    await waitFor(() => {
      expect(m.submit).toHaveBeenCalled();
    });
    const body = m.submit.mock.calls[0]?.[0];
    expect(body?.machine_id).toBe('m1');
    expect(body?.capture).toMatchObject({ reading: '1510', kind: 'DAILY', gps: { status: 'FIX' } });
    expect(body?.lines).toEqual([
      { kind: 'CUSTOMER', customer_id: 'c1', hours: '120' },
      { kind: 'NON_PRODUCTIVE', reason_id: 'r1', hours: '180', note: 'Hydraulic hose' },
    ]);
  });

  it('takes the reading only when the machine has no starting reading', async () => {
    m.context.mockResolvedValue({
      ...CONTEXT,
      previous_reading: null,
      previous_at: null,
      previous_source: null,
    });
    const user = userEvent.setup();
    renderWithProviders(<FieldMachineReportPage />, { tenantPermissions: [SUBMIT] });
    await user.click(await screen.findByRole('button', { name: 'New report' }));
    expect(await screen.findByText(/no starting reading yet/)).toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: /Capture mode/ }));
    await user.click(screen.getByRole('option', { name: /Manual/ }));
    await user.type(screen.getByRole('textbox', { name: /Meter reading/ }), '800');
    await waitFor(() => {
      expect(m.gps).toHaveBeenCalled();
    });
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('800 h (opening reading)')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Submit for approval' }));
    await waitFor(() => {
      expect(m.submit).toHaveBeenCalled();
    });
    expect(m.submit.mock.calls[0]?.[0]).toMatchObject({ lines: [], opening: true });
  });

  it('says when a report on the machine already waits for a decision', async () => {
    m.context.mockResolvedValue({ ...CONTEXT, pending_report_id: 'mr1' });
    const user = userEvent.setup();
    renderWithProviders(<FieldMachineReportPage />, { tenantPermissions: [SUBMIT] });
    await user.click(await screen.findByRole('button', { name: 'New report' }));
    expect(await screen.findByText(/waiting for a decision. The next report/)).toBeInTheDocument();
  });
});

function openDetail(perms: string[]) {
  renderWithProviders(
    <Routes>
      <Route path={ROUTES.tenantMachineReportDetail} element={<MachineReportDetailPage />} />
    </Routes>,
    { route: '/tenant/machine-reports/mr1', tenantPermissions: perms },
  );
}

describe('Approvals › Machine report detail', () => {
  it('shows the split with customers’ hours before and after, notes and the tracker check', async () => {
    openDetail([READ, APPROVE]);
    expect(await screen.findByText('140 h → 20 h left')).toBeInTheDocument();
    expect(screen.getByText('Hydraulic hose replaced on site')).toBeInTheDocument();
    expect(screen.getByText('296 h')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument();
  });

  it('hides Approve and Reject from the submitter and from readers', async () => {
    m.get.mockResolvedValue({ ...REPORT, submitted_by: ME });
    openDetail([READ, APPROVE]);
    expect(await screen.findByText(/someone else decides it/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
  });

  it('hides the decision without the approve permission', async () => {
    openDetail([READ]);
    await screen.findByText('140 h → 20 h left');
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });

  it('rejects only with a reason', async () => {
    const user = userEvent.setup();
    openDetail([READ, APPROVE]);
    await user.click(await screen.findByRole('button', { name: 'Reject' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Reject' }));
    expect(await within(dialog).findByText('A reason is required')).toBeInTheDocument();
    expect(m.reject).not.toHaveBeenCalled();
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'Split the transit');
    await user.click(within(dialog).getByRole('button', { name: 'Reject' }));
    await waitFor(() => {
      expect(m.reject).toHaveBeenCalled();
    });
    expect(m.reject.mock.calls[0]?.[1]).toEqual({ reason: 'Split the transit' });
  });

  it('explains the server refusing a decision on your own report', async () => {
    m.approve.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'SEGREGATION_OF_DUTIES',
        message: 'x',
        correlationId: null,
      }),
    );
    const user = userEvent.setup();
    openDetail([READ, APPROVE]);
    await user.click(await screen.findByRole('button', { name: 'Approve' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Approve' }));
    expect(
      await within(dialog).findByText(/submitted a report cannot decide it/),
    ).toBeInTheDocument();
  });

  it('offers the submitter a correction of a rejected report', async () => {
    m.get.mockResolvedValue({ ...REPORT, status: 'REJECTED', decision_note: 'Wrong customer' });
    openDetail([READ, SUBMIT]);
    expect(await screen.findByText(/Wrong customer/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Correct report' })).toBeInTheDocument();
  });
});

describe('Administration › Machine report reasons', () => {
  it('lists reasons and lets reason managers add one', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MachineReportReasonsPage />, {
      tenantPermissions: ['tenant.meter.reasons'],
    });
    expect(await screen.findByText('Breakdown / repair')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'New reason' }));
    await user.type(screen.getByRole('textbox', { name: /Code/ }), 'WEATHER');
    await user.type(screen.getByRole('textbox', { name: /^Name/ }), 'Weather');
    await user.click(screen.getByRole('button', { name: 'Add reason' }));
    await waitFor(() => {
      expect(m.createReason).toHaveBeenCalled();
    });
    expect(m.createReason.mock.calls[0]?.[0]).toEqual({
      code: 'WEATHER',
      name: 'Weather',
      description: null,
    });
  });

  it('is read-only without the reasons permission', async () => {
    renderWithProviders(<MachineReportReasonsPage />, {
      tenantPermissions: ['tenant.machine_report.read'],
    });
    expect(await screen.findByText('Breakdown / repair')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New reason' })).not.toBeInTheDocument();
  });
});

describe('notifications', () => {
  it('open the machine report and the credit invoice they are about', () => {
    expect(notificationTargetPath(null, { kind: 'MACHINE_REPORT', record_id: 'mr1' })).toBe(
      '/tenant/machine-reports/mr1',
    );
    expect(notificationTargetPath(null, { kind: 'CREDIT_INVOICE', record_id: 'i1' })).toBe(
      '/tenant/hours/credit-invoices/i1',
    );
  });
});
