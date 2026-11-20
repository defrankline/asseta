import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { useField } from 'formik';
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
import { MachineReportsPage } from './MachineReportsPage';
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
// "Pick <label>" stands in for choosing the typed id from the list.
vi.mock('../../../components/forms/FormikAsyncIdAutocomplete', () => ({
  FormikAsyncIdAutocomplete: ({
    name,
    label,
    resolveOption,
    onOptionChange,
  }: {
    name: string;
    label: string;
    resolveOption?: (id: string) => Promise<unknown>;
    onOptionChange?: (option: unknown) => void;
  }) => {
    const [field] = useField<string>(name);
    return (
      <>
        <FormikTextField name={name} label={label} />
        {onOptionChange !== undefined && resolveOption !== undefined && (
          <button
            type="button"
            onClick={() => {
              void resolveOption(field.value).then(onOptionChange);
            }}
          >
            Pick {label}
          </button>
        )}
      </>
    );
  },
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
    expect(within(table).getByText('Report due')).toBeInTheDocument();
    expect(within(table).getByText('Awaiting approval · MR-2026-00001')).toBeInTheDocument();
    // A rejected report is final: the machine is due again and takes a new report.
    expect(within(table).getByText('Report due · last report rejected')).toBeInTheDocument();
    expect(within(table).getAllByRole('button', { name: 'New report' })).toHaveLength(2);
    expect(screen.queryByRole('button', { name: 'Correct report' })).not.toBeInTheDocument();
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
    expect(screen.queryByText(/Time since last visit/)).not.toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Meter reading/ }), '1510');
    expect(screen.getByText('Hours to account for: 300 h')).toBeInTheDocument();
    expect(
      screen.getByText(
        /^Time since last visit: \d+ days?( \d+ h)? \(last visit 12 Nov, \d\d:\d\d\)$/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/Where: Mbezi Beach, Kinondoni \(at Yard\) ·/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '-6.8000, 39.2800' })).toHaveAttribute(
      'href',
      'https://www.openstreetmap.org/?mlat=-6.8&mlon=39.28#map=17/-6.8/39.28',
    );
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

  it("fills a customer's line with min(their hours left, hours still to account for)", async () => {
    const user = userEvent.setup();
    renderWithProviders(<FieldMachineReportPage />, { tenantPermissions: [SUBMIT, READ] });
    await user.click(await screen.findByRole('button', { name: 'New report' }));
    await user.click(await screen.findByRole('combobox', { name: /Capture mode/ }));
    await user.click(screen.getByRole('option', { name: /Manual/ }));
    await user.type(screen.getByRole('textbox', { name: /Meter reading/ }), '1510');
    await waitFor(() => {
      expect(m.gps).toHaveBeenCalled();
    });
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Add customer' }));
    const hours = () => screen.getAllByRole('textbox', { name: /^Hours/ });
    expect(hours()[0]).toHaveValue('300');
    await user.type(screen.getByRole('textbox', { name: /^Customer/ }), 'c1');
    // 300 h to account for, the customer has 140 h left → 140.
    await user.click(screen.getByRole('button', { name: 'Pick Customer' }));
    await waitFor(() => {
      expect(hours()[0]).toHaveValue('140');
    });
    expect(screen.getByText('160 h still to account for')).toBeInTheDocument();
    // Hours the supervisor typed are kept when the customer is picked again.
    await user.clear(hours()[0] as HTMLElement);
    await user.type(hours()[0] as HTMLElement, '100');
    await user.click(screen.getByRole('button', { name: 'Pick Customer' }));
    expect(hours()[0]).toHaveValue('100');
  });

  it('marks a line with invalid hours and does not count it as accounted for', async () => {
    const user = userEvent.setup();
    renderWithProviders(<FieldMachineReportPage />, { tenantPermissions: [SUBMIT, READ] });
    await user.click(await screen.findByRole('button', { name: 'New report' }));
    await user.click(await screen.findByRole('combobox', { name: /Capture mode/ }));
    await user.click(screen.getByRole('option', { name: /Manual/ }));
    await user.type(screen.getByRole('textbox', { name: /Meter reading/ }), '1219');
    await waitFor(() => {
      expect(m.gps).toHaveBeenCalled();
    });
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Add customer' }));
    await user.type(screen.getByRole('textbox', { name: /^Customer/ }), 'c1');
    const hours = () => screen.getAllByRole('textbox', { name: /^Hours/ });
    await user.clear(hours()[0] as HTMLElement);
    await user.type(hours()[0] as HTMLElement, '7.85');
    expect(screen.getByText('1.15 h still to account for')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Add non-productive' }));
    expect(hours()[1]).toHaveValue('1.15');
    await user.type(screen.getByRole('textbox', { name: /^Reason/ }), 'r1');
    await user.type(screen.getByRole('textbox', { name: /What happened/ }), 'Waiting');
    expect(screen.getByText('Every hour is accounted for.')).toBeInTheDocument();
    // A third decimal: the line is marked and its hours no longer count.
    await user.type(hours()[1] as HTMLElement, '5');
    expect(await screen.findByText('Hours have at most 2 decimals')).toBeInTheDocument();
    expect(screen.queryByText('Every hour is accounted for.')).not.toBeInTheDocument();
    expect(screen.getByText('1.15 h still to account for')).toBeInTheDocument();
    expect(screen.getByText(/Accounted for 7.85 h/)).toBeInTheDocument();
    // On the customer line: 140 h available, after this 132.15 h.
    expect(screen.getByText('Available 140 h · after this 132.15 h')).toBeInTheDocument();
  });

  it('takes the reading only when the machine has no starting reading', async () => {
    m.context.mockResolvedValue({
      ...CONTEXT,
      opening_required: true,
      previous_reading: null,
      previous_at: null,
      previous_source: null,
    });
    m.submit.mockRejectedValueOnce(
      new ApiError({
        status: 422,
        code: 'OPENING_NOT_ALLOWED',
        message: 'x',
        correlationId: null,
      }),
    );
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
    expect(await screen.findByText(/already has a starting reading/)).toBeInTheDocument();
    expect(m.submit.mock.calls[0]?.[0]).toMatchObject({
      machine_id: 'm1',
      opening: true,
      lines: [],
      capture: { kind: 'DAILY', machine_id: 'm1', reading: '800' },
    });
    expect(m.submit.mock.calls[0]?.[0]).not.toHaveProperty('capture_id');
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

  it('shows the time since the last visit and where both readings were taken', async () => {
    openDetail([READ]);
    // 27 h since the last visit, over the default 24 h warning.
    expect(await screen.findByText('Since last visit: 1 day 3 h')).toBeInTheDocument();
    expect(screen.getByText(/^Where: Mbezi Beach, Kinondoni ·/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '-6.8000, 39.2800' })).toHaveAttribute(
      'target',
      '_blank',
    );
    expect(
      screen.getByText(/^Last visit: \d+ Nov, \d\d:\d\d · Where: at Yard ·/),
    ).toBeInTheDocument();
    expect(screen.getByText('(±5 m)', { exact: false })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '-6.7924, 39.2083' })).toHaveAttribute(
      'href',
      'https://www.openstreetmap.org/?mlat=-6.7924&mlon=39.2083#map=17/-6.7924/39.2083',
    );
  });

  it('says "First visit" for a machine visited for the first time', async () => {
    m.get.mockResolvedValue({
      ...REPORT,
      previous_visit_at: null,
      since_previous_visit_seconds: null,
      previous_visit_lat: null,
      previous_visit_lng: null,
    });
    openDetail([READ]);
    expect(await screen.findByText('Since last visit: First visit')).toBeInTheDocument();
    expect(screen.queryByText(/^Last visit:/)).not.toBeInTheDocument();
  });

  it('rejects only with a reason', async () => {
    const user = userEvent.setup();
    openDetail([READ, APPROVE]);
    await user.click(await screen.findByRole('button', { name: 'Reject' }));
    const dialog = await screen.findByRole('dialog');
    expect(
      within(dialog).getByText(
        'The supervisor is told your reason. A rejected report is kept as a record; the supervisor sends a new report with a new reading.',
      ),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Reject' }));
    expect(await within(dialog).findByText('A reason is required')).toBeInTheDocument();
    expect(m.reject).not.toHaveBeenCalled();
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'Split the transit');
    await user.click(within(dialog).getByRole('button', { name: 'Reject' }));
    await waitFor(() => {
      expect(m.reject).toHaveBeenCalled();
    });
    expect(m.reject.mock.calls[0]?.[1]).toEqual({ reason: 'Split the transit' });
    expect(
      await screen.findByText('Report rejected. The supervisor will send a new report.'),
    ).toBeInTheDocument();
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

  it('shows a rejected report read-only, with the approver’s reason', async () => {
    m.get.mockResolvedValue({
      ...REPORT,
      status: 'REJECTED',
      decided_by_name: 'Asha Owner',
      decided_at: '2026-11-16T06:00:00Z',
      decision_note: 'Wrong customer',
    });
    openDetail([READ, SUBMIT, APPROVE]);
    expect(await screen.findByText('Rejected by Asha Owner: “Wrong customer”')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Correct report' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
    expect(screen.queryByText(/correct/i)).not.toBeInTheDocument();
  });
});

describe('Approvals › Machine reports list', () => {
  it('shows the time since the last visit, flagged over the company warning', async () => {
    m.list.mockResolvedValue(
      page([
        REPORT,
        {
          ...REPORT,
          id: 'mr2',
          report_number: 'MR-2026-00002',
          since_previous_visit_seconds: 5 * 3600 + 20 * 60,
        },
        {
          ...REPORT,
          id: 'mr3',
          report_number: 'MR-2026-00003',
          since_previous_visit_seconds: null,
        },
      ]),
    );
    renderWithProviders(<MachineReportsPage />, { tenantPermissions: [READ, APPROVE] });
    expect(
      await screen.findByRole('columnheader', { name: 'Since last visit' }),
    ).toBeInTheDocument();
    const late = await screen.findByText('1 day 3 h');
    expect(late).toHaveClass('MuiTypography-root');
    expect(getComputedStyle(late).fontWeight).toBe('600');
    expect(getComputedStyle(screen.getByText('5 h 20 min')).fontWeight).not.toBe('600');
    expect(screen.getByText('First visit')).toBeInTheDocument();
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
