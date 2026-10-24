import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { engineHoursService } from '../../../api/services/engineHoursService';
import type {
  BaselineDto,
  EngineHourReasonDto,
  IntervalDto,
  LedgerPointDto,
  MachineEngineHoursDto,
  Page,
  UnallocatedSegmentDto,
} from '../../../api/types';
import { MACHINE, MACHINE_ID, ME_ID } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { EngineHourReasonsPage } from './EngineHourReasonsPage';
import { MachineEngineHoursPanel } from './MachineEngineHoursPanel';
import { MeterBaselinesPage } from './MeterBaselinesPage';
import { UnallocatedHoursPage } from './UnallocatedHoursPage';

const mocks = vi.hoisted(() => ({
  listBaselines: vi.fn<typeof engineHoursService.listBaselines>(),
  decideBaseline: vi.fn<typeof engineHoursService.decideBaseline>(),
  machine: vi.fn<typeof engineHoursService.machine>(),
  listUnallocated: vi.fn<typeof engineHoursService.listUnallocated>(),
  listReasons: vi.fn<typeof engineHoursService.listReasons>(),
  getReason: vi.fn<typeof engineHoursService.getReason>(),
  createReason: vi.fn<typeof engineHoursService.createReason>(),
  proposeClassification: vi.fn<typeof engineHoursService.proposeClassification>(),
}));
vi.mock('../../../api/services/engineHoursService', () => ({ engineHoursService: mocks }));
vi.mock('../../../api/services/machineService', () => ({
  machineService: {
    list: vi.fn().mockResolvedValue({ items: [MACHINE], total: 1, page: 1, page_size: 20 }),
  },
}));

const OTHER = '44444444-4444-4444-8444-444444444444';

const page = <T,>(items: T[]): Page<T> => ({ items, total: items.length, page: 1, page_size: 25 });

function makeBaseline(overrides: Partial<BaselineDto> = {}): BaselineDto {
  return {
    id: 'bbbbbbbb-0000-4000-8000-000000000001',
    machine_id: MACHINE_ID,
    machine_code: 'EX-01',
    machine_name: 'Excavator',
    reading: '1000.0',
    captured_at: '2026-10-20T06:00:00Z',
    source: 'CAPTURE',
    source_capture_id: null,
    photo_attachment_id: null,
    latitude: null,
    longitude: null,
    accuracy_m: null,
    note: null,
    status: 'PROPOSED',
    proposed_by: OTHER,
    proposed_at: '2026-10-20T06:01:00Z',
    decided_by: null,
    decided_at: null,
    decision_note: null,
    ...overrides,
  };
}

const point = (ref: string, reading: string, at: string, source = 'DAILY'): LedgerPointDto => ({
  ref,
  reading,
  at,
  source,
  job_id: null,
});

const START = point(
  '11111111-0000-4000-8000-000000000001',
  '1000.0',
  '2026-10-20T06:00:00Z',
  'BASELINE',
);
const END = point('11111111-0000-4000-8000-000000000002', '1012.5', '2026-10-21T18:00:00Z');

function makeInterval(overrides: Partial<IntervalDto> = {}): IntervalDto {
  return {
    machine_id: MACHINE_ID,
    start: START,
    end: END,
    hours: '12.5',
    raw_hours: '12.5',
    reset_applied: false,
    inconsistent: false,
    review: 'VERIFIED',
    opened_at: '2026-10-21T18:00:00Z',
    age_days: 2,
    overlapping_job_ids: [],
    segments: [
      {
        kind: 'CUSTOMER_WORK',
        hours: '10.0',
        classification: 'NOT_APPLICABLE',
        job_id: 'dddddddd-0000-4000-8000-000000000001',
        job_number: 'J-100',
        approved: null,
        proposal: null,
      },
      {
        kind: 'UNALLOCATED',
        hours: '2.5',
        classification: 'UNEXPLAINED',
        job_id: null,
        job_number: null,
        approved: null,
        proposal: null,
      },
    ],
    ...overrides,
  };
}

const TOTALS = {
  total_hours: '12.5',
  customer_work_hours: '10.0',
  unallocated_hours: '2.5',
  unexplained_hours: '2.5',
  proposed_hours: '0',
  approved_non_customer_hours: '0',
  identified_variance_hours: '0',
  pending_review_hours: '0',
};

function makeLedger(overrides: Partial<MachineEngineHoursDto> = {}): MachineEngineHoursDto {
  return {
    machine_id: MACHINE_ID,
    machine_code: 'EX-01',
    machine_name: 'Excavator',
    status: 'UNEXPLAINED',
    baseline: makeBaseline({
      status: 'APPROVED',
      decided_by: OTHER,
      decided_at: '2026-10-20T07:00:00Z',
    }),
    baseline_proposal: null,
    intervals: [makeInterval()],
    totals: TOTALS,
    overlaps: [],
    policy_version: 'EH:P1',
    ...overrides,
  };
}

const REASON: EngineHourReasonDto = {
  id: 'cccccccc-0000-4000-8000-000000000001',
  kind: 'NON_CUSTOMER_CATEGORY',
  code: 'MAINT',
  name: 'Maintenance',
  description: null,
  is_active: true,
  version: 1,
  deactivated_at: null,
  deactivation_reason: null,
};

function makeSegment(overrides: Partial<UnallocatedSegmentDto> = {}): UnallocatedSegmentDto {
  return {
    machine_id: MACHINE_ID,
    machine_code: 'EX-01',
    machine_name: 'Excavator',
    start: START,
    end: END,
    hours: '2.5',
    review: 'VERIFIED',
    classification: 'UNEXPLAINED',
    opened_at: '2026-10-21T18:00:00Z',
    age_days: 4,
    investigation_due: true,
    approved: null,
    proposal: null,
    ...overrides,
  };
}

beforeEach(() => {
  mocks.listReasons.mockResolvedValue(page([REASON]));
  mocks.getReason.mockResolvedValue(REASON);
});

describe('MeterBaselinesPage', () => {
  const APPROVER = ['tenant.meter.read', 'tenant.meter.approve', 'tenant.machine.read'];

  it('lists proposals awaiting a decision and blocks deciding your own', async () => {
    mocks.listBaselines.mockResolvedValue(
      page([
        makeBaseline(),
        makeBaseline({ id: 'bbbbbbbb-0000-4000-8000-000000000002', proposed_by: ME_ID }),
      ]),
    );
    renderWithProviders(<MeterBaselinesPage />, { tenantPermissions: APPROVER });
    await screen.findAllByText('EX-01 · Excavator');
    expect(mocks.listBaselines).toHaveBeenCalledWith(
      expect.objectContaining({
        filters: expect.objectContaining({ status: 'PROPOSED' }) as unknown,
      }),
      expect.any(AbortSignal),
    );
    expect(
      screen.getByRole('button', { name: 'Decide (Someone else must decide your own request)' }),
    ).toBeDisabled();
    // Proposing needs the capture permission.
    expect(screen.queryByRole('button', { name: 'Propose baseline' })).not.toBeInTheDocument();
  });

  it('records a decision with the required note', async () => {
    const user = userEvent.setup();
    mocks.listBaselines.mockResolvedValue(page([makeBaseline()]));
    mocks.decideBaseline.mockResolvedValue(makeBaseline({ status: 'APPROVED' }));
    renderWithProviders(<MeterBaselinesPage />, { tenantPermissions: APPROVER });
    await user.click(await screen.findByRole('button', { name: 'Decide' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Approve' }));
    await user.type(within(dialog).getByRole('textbox', { name: /Note/ }), 'Photo checked');
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(mocks.decideBaseline).toHaveBeenCalledWith(
        makeBaseline().id,
        { decision: 'APPROVE', note: 'Photo checked' },
        expect.any(String),
      );
    });
    expect(await screen.findByText('Baseline approved.')).toBeInTheDocument();
  });
});

describe('MachineEngineHoursPanel', () => {
  it('shows totals, the interval breakdown and lets a reviewer explain the open hours', async () => {
    const user = userEvent.setup();
    mocks.machine.mockResolvedValue(makeLedger());
    mocks.proposeClassification.mockResolvedValue({
      id: 'eeeeeeee-0000-4000-8000-000000000001',
      machine_id: MACHINE_ID,
      start_ref: START.ref,
      end_ref: END.ref,
      start_at: START.at,
      end_at: END.at,
      hours: '2.5',
      outcome: 'APPROVED_NON_CUSTOMER',
      reason_id: REASON.id,
      note: 'Moved to site B',
      status: 'PROPOSED',
      proposed_by: ME_ID,
      proposed_at: '2026-10-22T08:00:00Z',
      decided_by: null,
      decided_at: null,
      decision_note: null,
      policy_version: 'EH:P1',
    });
    renderWithProviders(<MachineEngineHoursPanel machineId={MACHINE_ID} />, {
      tenantPermissions: ['tenant.meter.read', 'tenant.meter.review'],
    });
    const table = await screen.findByRole('table', { name: 'Engine-hour intervals' });
    expect(within(table).getByText('Job J-100 · 10.0 h')).toBeInTheDocument();
    expect(within(table).getByText('Not yet explained · 2.5 h')).toBeInTheDocument();
    expect(screen.getByText('Hours to explain')).toBeInTheDocument();
    await user.click(within(table).getByRole('button', { name: 'Explain' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /What were these hours/ }));
    await user.click(await screen.findByRole('option', { name: /^Non-customer activity/ }));
    await user.click(await within(dialog).findByRole('combobox', { name: /Activity category/ }));
    await user.click(await screen.findByRole('option', { name: 'MAINT · Maintenance' }));
    await user.type(
      within(dialog).getByRole('textbox', { name: /What happened/ }),
      'Moved to site B',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Propose explanation' }));
    await waitFor(() => {
      expect(mocks.proposeClassification).toHaveBeenCalledWith(
        {
          machine_id: MACHINE_ID,
          start_ref: START.ref,
          end_ref: END.ref,
          outcome: 'APPROVED_NON_CUSTOMER',
          reason_id: REASON.id,
          note: 'Moved to site B',
        },
        expect.any(String),
      );
    });
    expect(mocks.listReasons).toHaveBeenCalledWith(
      expect.objectContaining({ filters: { kind: 'NON_CUSTOMER_CATEGORY' } }),
      expect.any(AbortSignal),
    );
  });

  it('offers a baseline proposal when the machine has none, and no Explain without review', async () => {
    mocks.machine.mockResolvedValue(
      makeLedger({ status: 'NO_BASELINE', baseline: null, intervals: [] }),
    );
    renderWithProviders(<MachineEngineHoursPanel machineId={MACHINE_ID} />, {
      tenantPermissions: ['tenant.meter.read', 'tenant.meter.capture'],
    });
    expect(await screen.findByRole('button', { name: 'Propose baseline' })).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Use an existing reading' }),
    ).not.toBeInTheDocument();
    expect(screen.getAllByText('No approved baseline').length).toBeGreaterThan(0);
  });
});

describe('UnallocatedHoursPage', () => {
  it('lists open items oldest first with age and hides Explain for readers', async () => {
    mocks.listUnallocated.mockResolvedValue(page([makeSegment()]));
    renderWithProviders(<UnallocatedHoursPage />, { tenantPermissions: ['tenant.meter.read'] });
    expect(await screen.findByText('EX-01 · Excavator')).toBeInTheDocument();
    expect(screen.getByText('Investigation opened')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Explain' })).not.toBeInTheDocument();
  });
});

describe('EngineHourReasonsPage', () => {
  it('creates a list entry', async () => {
    const user = userEvent.setup();
    mocks.createReason.mockResolvedValue({ ...REASON, code: 'RELOC', name: 'Relocation' });
    renderWithProviders(<EngineHourReasonsPage />, {
      tenantPermissions: ['tenant.meter.read', 'tenant.meter.reasons'],
    });
    await screen.findByText('MAINT');
    await user.click(screen.getByRole('button', { name: 'New entry' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /List/ }));
    await user.click(await screen.findByRole('option', { name: 'Non-customer activity category' }));
    await user.type(within(dialog).getByRole('textbox', { name: /Code/ }), 'RELOC');
    await user.type(within(dialog).getByRole('textbox', { name: /^Name/ }), 'Relocation');
    await user.click(within(dialog).getByRole('button', { name: 'Create entry' }));
    await waitFor(() => {
      expect(mocks.createReason).toHaveBeenCalledWith(
        { kind: 'NON_CUSTOMER_CATEGORY', code: 'RELOC', name: 'Relocation', description: null },
        expect.any(String),
      );
    });
  });

  it('is read-only without the manage permission', async () => {
    renderWithProviders(<EngineHourReasonsPage />, { tenantPermissions: ['tenant.meter.read'] });
    await screen.findByText('MAINT');
    expect(screen.queryByRole('button', { name: 'New entry' })).not.toBeInTheDocument();
  });
});
