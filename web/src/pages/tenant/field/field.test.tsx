import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { cashService } from '../../../api/services/cashService';
import type { customerService } from '../../../api/services/customerService';
import type { jobService } from '../../../api/services/jobService';
import type { meterService } from '../../../api/services/meterService';
import type { policyService } from '../../../api/services/policyService';
import { CUSTOMER, makePayment, page } from '../../../test/financeFixtures';
import {
  CONTRACT,
  JOB_ID,
  MACHINE,
  makeCapture,
  makeJob,
  makeSummary,
} from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { FieldCollectionDialog } from './FieldCollectionDialog';
import { FieldJobPage } from './FieldJobPage';
import { MyJobsPage } from './MyJobsPage';

const mocks = vi.hoisted(() => ({
  summary: vi.fn<typeof jobService.summary>(),
  list: vi.fn<typeof jobService.list>(),
  listAcknowledgements: vi.fn<typeof jobService.listAcknowledgements>(),
  listActivities: vi.fn<typeof jobService.listActivities>(),
  fieldMachines: vi.fn<typeof jobService.fieldMachines>(),
  listCaptures: vi.fn<typeof meterService.listCaptures>(),
  listExceptions: vi.fn<typeof meterService.listExceptions>(),
  submitCapture: vi.fn<typeof meterService.submitCapture>(),
  upload: vi.fn<typeof meterService.upload>(),
  effective: vi.fn<typeof policyService.effective>(),
  getContract: vi.fn<typeof customerService.getContract>(),
  getCustomer: vi.fn<typeof customerService.get>(),
  listCustomers: vi.fn<typeof customerService.list>(),
  recordCollection: vi.fn<typeof cashService.recordCollection>(),
}));
vi.mock('../../../api/services/jobService', () => ({
  jobService: {
    summary: mocks.summary,
    list: mocks.list,
    listAcknowledgements: mocks.listAcknowledgements,
    listActivities: mocks.listActivities,
    fieldMachines: mocks.fieldMachines,
  },
}));
vi.mock('../../../api/services/meterService', () => ({
  meterService: {
    listCaptures: mocks.listCaptures,
    listExceptions: mocks.listExceptions,
    submitCapture: mocks.submitCapture,
    upload: mocks.upload,
  },
}));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { effective: mocks.effective },
}));
vi.mock('../../../api/services/customerService', () => ({
  customerService: {
    getContract: mocks.getContract,
    get: mocks.getCustomer,
    list: mocks.listCustomers,
  },
}));
vi.mock('../../../api/services/cashService', () => ({
  cashService: { recordCollection: mocks.recordCollection },
}));

/** The seeded Supervisor role (no office oversight, no machine register). */
const SUPERVISOR = [
  'tenant.job.read',
  'tenant.job.log',
  'tenant.meter.capture',
  'tenant.meter.read',
  'tenant.customer.read',
  'tenant.expense.read',
  'tenant.expense.write',
  'tenant.collection.record',
];

beforeEach(() => {
  mocks.fieldMachines.mockResolvedValue([MACHINE]);
  mocks.listAcknowledgements.mockResolvedValue([]);
  mocks.listActivities.mockResolvedValue([]);
  mocks.listCaptures.mockResolvedValue([]);
  mocks.listExceptions.mockResolvedValue(page([]));
  mocks.effective.mockResolvedValue({
    policy_type: 'METER_CAPTURE',
    version_stamp: 'MC:P1',
    values: { opening_mode: 'MANUAL', closing_mode: 'MANUAL', manual_photo_required: false },
  });
});

function renderWorkspace(permissions = SUPERVISOR) {
  renderWithProviders(
    <Routes>
      <Route path="/tenant/field/jobs/:jobId" element={<FieldJobPage />} />
    </Routes>,
    { tenantPermissions: permissions, route: `/tenant/field/jobs/${JOB_ID}` },
  );
}

describe('FieldJobPage', () => {
  it('records the opening reading from a laptop and shows the server verdict', async () => {
    const user = userEvent.setup();
    const approved = makeJob({ status: 'APPROVED' });
    mocks.summary.mockResolvedValue(
      makeSummary({ job: approved, opening_reading: null, closing_reading: null }),
    );
    mocks.submitCapture.mockResolvedValue({
      capture: makeCapture({ state: 'PROVISIONAL', reading: '1200.4', gps_status: 'DISABLED' }),
      findings: [
        {
          type: 'GPS_UNAVAILABLE',
          severity: 'WARNING',
          blocking: true,
          evidence: { gps_status: 'DISABLED', enforcement: 'SOFT' },
        },
      ],
    });
    renderWorkspace();
    expect(await screen.findByText(/Record the opening meter reading/)).toBeInTheDocument();
    expect(screen.getByText('Approved · EX-01 · Excavator')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Start job' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Record opening reading' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/Photograph the hour meter/)).toBeInTheDocument();
    // A supervisor reads the capture policy they capture under (no tenant.policy.read).
    expect(
      await within(dialog).findByText('Policy requires Manual for this reading'),
    ).toBeVisible();
    expect(await within(dialog).findByText('Location disabled')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('combobox', { name: /Capture mode/ }));
    await user.click(await screen.findByRole('option', { name: 'Manual (numeric entry)' }));
    await user.type(within(dialog).getByRole('textbox', { name: /Meter reading/ }), '1200.4');
    await user.click(within(dialog).getByRole('button', { name: 'Submit reading' }));

    await waitFor(() => {
      expect(mocks.submitCapture).toHaveBeenCalledTimes(1);
    });
    expect(mocks.submitCapture.mock.calls[0]?.[0]).toMatchObject({
      job_id: JOB_ID,
      kind: 'OPENING',
      reading: '1200.4',
      gps: { status: 'DISABLED', provider: 'browser' },
    });
    const result = await screen.findByRole('alert', { name: 'Reading result' });
    expect(within(result).getByText('GPS unavailable')).toBeInTheDocument();
    expect(within(result).getByText(/listed for office review/)).toBeInTheDocument();
  });

  it('asks for the customer acknowledgement once the closing reading exists', async () => {
    mocks.summary.mockResolvedValue(
      makeSummary({ job: makeJob({ status: 'IN_PROGRESS' }), closing_reading: '1208.8' }),
    );
    mocks.listActivities.mockResolvedValue([
      {
        id: 'a1',
        client_id: 'c1',
        activity_type: 'DOWNTIME',
        started_at: '2026-10-21T08:00:00Z',
        ended_at: '2026-10-21T09:30:00Z',
        billable: false,
        note: 'Hydraulic hose',
      },
    ]);
    renderWorkspace();
    expect(
      await screen.findByRole('button', { name: 'Record customer acknowledgement' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Complete job' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Work log totals')).toHaveTextContent(/Downtime 1 h 30 min/);
    expect(screen.getByRole('button', { name: 'Log work' })).toBeInTheDocument();
  });

  it('offers Complete job when the closing reading and acknowledgement are recorded', async () => {
    mocks.summary.mockResolvedValue(
      makeSummary({ job: makeJob({ status: 'IN_PROGRESS' }), closing_reading: '1208.8' }),
    );
    mocks.listAcknowledgements.mockResolvedValue([
      {
        id: 'k1',
        method: 'NAME_CONFIRMATION',
        signer_name: 'Site Manager',
        signer_phone: null,
        signature_attachment_id: null,
        acknowledged_hours: null,
        captured_at: '2026-10-21T16:00:00Z',
      },
    ]);
    renderWorkspace();
    expect(await screen.findByRole('button', { name: 'Complete job' })).toBeInTheDocument();
  });
});

describe('MyJobsPage', () => {
  beforeEach(() => {
    mocks.list.mockImplementation((query) =>
      Promise.resolve(
        page(
          query.filters?.status === 'IN_PROGRESS'
            ? [makeJob({ status: 'IN_PROGRESS', job_number: 'J-RUN' })]
            : [],
        ),
      ),
    );
  });

  it('lists only the supervisor’s own jobs, grouped by stage', async () => {
    renderWithProviders(<MyJobsPage />, { tenantPermissions: SUPERVISOR });
    const running = await screen.findByRole('region', { name: 'In progress' });
    expect(within(running).getByText('J-RUN')).toBeInTheDocument();
    expect(within(running).getByText('EX-01 · Excavator')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Ready to start' })).toHaveTextContent(
      'No approved job is waiting to start.',
    );
    const statuses = mocks.list.mock.calls.map(([q]) => [q.filters?.status, q.filters?.mine]);
    expect(statuses).toEqual([
      ['IN_PROGRESS', 'true'],
      ['APPROVED', 'true'],
      ['COMPLETED', 'true'],
    ]);
    expect(screen.queryByRole('group', { name: 'Jobs shown' })).not.toBeInTheDocument();
  });

  it('lets job managers switch between all jobs and their own', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MyJobsPage />, {
      tenantPermissions: [...SUPERVISOR, 'tenant.job.approve'],
    });
    await screen.findByRole('region', { name: 'In progress' });
    expect(mocks.list.mock.calls.every(([q]) => q.filters?.mine === undefined)).toBe(true);
    await user.click(screen.getByRole('button', { name: 'Assigned to me' }));
    await waitFor(() => {
      expect(mocks.list.mock.calls.at(-1)?.[0].filters?.mine).toBe('true');
    });
  });
});

describe('FieldCollectionDialog', () => {
  it('fills the customer from the picked job and records into the caller’s own custody', async () => {
    const user = userEvent.setup();
    const job = makeJob({ status: 'IN_PROGRESS' });
    mocks.list.mockResolvedValue(page([job]));
    mocks.summary.mockResolvedValue(makeSummary({ job }));
    mocks.getContract.mockResolvedValue(CONTRACT);
    mocks.getCustomer.mockResolvedValue(CUSTOMER);
    mocks.recordCollection.mockResolvedValue(makePayment());
    const onRecorded = vi.fn();
    renderWithProviders(
      <FieldCollectionDialog timeZone="UTC" onClose={vi.fn()} onRecorded={onRecorded} />,
      { tenantPermissions: SUPERVISOR },
    );
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /^Job/ }));
    await user.click(await screen.findByRole('option', { name: /J-100/ }));
    await waitFor(() => {
      expect(within(dialog).getByRole('combobox', { name: /^Customer/ })).toHaveValue(
        'ACME · Acme Builders',
      );
    });
    expect(mocks.list.mock.calls[0]?.[0].filters).toEqual({ mine: 'true' });
    await user.type(within(dialog).getByRole('textbox', { name: /^Amount received/ }), '250000');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Next' }));
    expect(await within(dialog).findByText('Me (my custody)')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Record collection' }));
    await waitFor(() => {
      expect(mocks.recordCollection).toHaveBeenCalledWith(
        expect.objectContaining({
          customer_id: CONTRACT.customer_id,
          amount: '250000',
          staff_member_id: null,
          allocations: [],
        }),
        expect.any(String),
      );
    });
    expect(mocks.recordCollection.mock.calls[0]?.[0]).not.toHaveProperty('job_id');
    expect(onRecorded).toHaveBeenCalledTimes(1);
  });
});
