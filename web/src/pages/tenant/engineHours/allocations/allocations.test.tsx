import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  AllocationCorrectionDto,
  AllocationDayDto,
  WorkAllocationDto,
} from '../../../../api/allocationTypes';
import type { allocationService } from '../../../../api/services/allocationService';
import type { Page } from '../../../../api/types';
import { notificationTargetPath } from '../../../../notifications/center/display';
import { recordPath, recordRoutePattern } from '../../../../navigation/recordRoutes';
import { MACHINE_ID, ME_ID } from '../../../../test/jobFixtures';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { AllocationCorrectionDialog } from './AllocationCorrectionDialog';
import {
  AllocationCorrectionDetailPage,
  WorkAllocationDetailPage,
} from './WorkAllocationDetailPages';
import { WorkAllocationsPage } from './WorkAllocationsPage';

const m = vi.hoisted(() => ({
  list: vi.fn<typeof allocationService.list>(),
  get: vi.fn<typeof allocationService.get>(),
  reconciliation: vi.fn<typeof allocationService.reconciliation>(),
  proposeCorrection: vi.fn<typeof allocationService.proposeCorrection>(),
  getCorrection: vi.fn<typeof allocationService.getCorrection>(),
  decideCorrection: vi.fn<typeof allocationService.decideCorrection>(),
}));
vi.mock('../../../../api/services/allocationService', () => ({ allocationService: m }));

const OTHER = '44444444-4444-4444-8444-444444444444';
const A_ID = 'aaaaaaaa-0000-4000-8000-000000000001';
const OLD_ID = 'aaaaaaaa-0000-4000-8000-000000000002';
const GROUP = 'bbbbbbbb-0000-4000-8000-000000000001';

const entry = (o: Partial<WorkAllocationDto> = {}): WorkAllocationDto => ({
  id: A_ID,
  machine_id: MACHINE_ID,
  machine_code: 'EX-01',
  machine_name: 'Excavator',
  work_date: '2026-11-02',
  meter_epoch: 0,
  start_ref: 'cccccccc-0000-4000-8000-000000000001',
  start_reading: '1000.00',
  start_at: '2026-11-02T06:00:00Z',
  end_ref: 'cccccccc-0000-4000-8000-000000000002',
  end_reading: '1006.00',
  end_at: '2026-11-02T12:00:00Z',
  hours: '6.00',
  kind: 'CUSTOMER_WORK',
  customer_id: 'dddddddd-0000-4000-8000-000000000001',
  customer_name: 'Acme Quarry',
  job_id: 'dddddddd-0000-4000-8000-000000000002',
  job_number: 'J-100',
  activity_type: null,
  reason_id: null,
  reason_name: null,
  lots: [
    {
      purchase_id: 'eeeeeeee-0000-4000-8000-000000000001',
      purchase_number: 'HP-7',
      hours: '6.00',
    },
  ],
  evidence_attachment_ids: [],
  source: 'DERIVED',
  reading_review: 'VERIFIED',
  changeover_id: null,
  classification_id: null,
  status: 'ACTIVE',
  supersedes_id: null,
  superseded_by_ids: [],
  correction_group_id: null,
  correction_reason: null,
  recorded_by: OTHER,
  recorded_by_name: 'Sam Supervisor',
  decided_by: null,
  decided_at: null,
  decision_note: null,
  superseded_at: null,
  policy_version: 'EH:P1',
  created_at: '2026-11-02T13:00:00Z',
  ...o,
});

const page = (items: WorkAllocationDto[]): Page<WorkAllocationDto> => ({
  items,
  total: items.length,
  page: 1,
  page_size: 20,
});

const day = (o: Partial<AllocationDayDto> = {}): AllocationDayDto => ({
  machine_id: MACHINE_ID,
  machine_code: 'EX-01',
  machine_name: 'Excavator',
  day: '2026-11-02',
  total_engine_hours: '10.00',
  customer_hours: '6.00',
  authorized_hours: '3.00',
  unexplained_hours: '1.00',
  allocated_hours: '10.00',
  difference_hours: '0.00',
  reconciled: true,
  ...o,
});

const correction = (o: Partial<AllocationCorrectionDto> = {}): AllocationCorrectionDto => ({
  group_id: GROUP,
  status: 'PROPOSED',
  supersedes_id: A_ID,
  entries: [
    entry({
      id: OLD_ID,
      status: 'PROPOSED',
      correction_group_id: GROUP,
      correction_reason: 'Second customer from noon',
      recorded_by: ME_ID,
      recorded_by_name: 'Me',
    }),
  ],
  ...o,
});

beforeEach(() => {
  vi.clearAllMocks();
  m.list.mockResolvedValue(page([entry()]));
  m.reconciliation.mockResolvedValue([]);
});

describe('WorkAllocationsPage', () => {
  it('lists entries with kind chips and lots, and filters by kind', async () => {
    const user = userEvent.setup();
    renderWithProviders(<WorkAllocationsPage />, { tenantPermissions: ['tenant.meter.read'] });
    expect(await screen.findByText('Acme Quarry · J-100')).toBeInTheDocument();
    expect(screen.getByText('HP-7 · 6.00 h')).toBeInTheDocument();
    expect(screen.getAllByText('Customer work').length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: 'Unexplained' }));
    await waitFor(() => {
      expect(m.list.mock.lastCall?.[0].filters).toMatchObject({
        kind: 'UNEXPLAINED',
        status: 'ACTIVE',
      });
    });
  });

  it('shows the day balance and highlights a difference', async () => {
    const user = userEvent.setup();
    m.reconciliation.mockResolvedValue([
      day(),
      day({
        day: '2026-11-03',
        difference_hours: '2.00',
        allocated_hours: '8.00',
        reconciled: false,
      }),
    ]);
    renderWithProviders(<WorkAllocationsPage />, { tenantPermissions: ['tenant.meter.read'] });
    await user.click(screen.getByRole('tab', { name: 'Per-day reconciliation' }));
    expect(await screen.findByText('Difference 2.00 h')).toBeInTheDocument();
    expect(screen.getByText('Reconciled')).toBeInTheDocument();
    expect(screen.getByText(/customer \+ authorized \+ unexplained/)).toBeInTheDocument();
  });
});

describe('AllocationCorrectionDialog', () => {
  const open = () => {
    const onProposed = vi.fn();
    renderWithProviders(
      <AllocationCorrectionDialog
        allocation={entry({ kind: 'UNEXPLAINED', customer_id: null, job_id: null, lots: [] })}
        onClose={vi.fn()}
        onProposed={onProposed}
      />,
      { tenantPermissions: ['tenant.meter.review'] },
    );
    return onProposed;
  };

  it('refuses parts that do not total the original', async () => {
    const user = userEvent.setup();
    open();
    const hours = screen.getByRole('textbox', { name: /Hours/ });
    await user.clear(hours);
    await user.type(hours, '4');
    expect(screen.getByText(/Parts total 4.00 of 6.00 h \(2.00 h short\)/)).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Wrong customer');
    await user.click(screen.getByRole('button', { name: 'Propose correction' }));
    expect(await screen.findByText('The parts must total 6.00 h')).toBeInTheDocument();
    expect(m.proposeCorrection).not.toHaveBeenCalled();
  });

  it('sends the parts and the reason when they total the original', async () => {
    const user = userEvent.setup();
    const onProposed = open();
    m.proposeCorrection.mockResolvedValue(correction());
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Standing idle, no work');
    await user.click(screen.getByRole('button', { name: 'Propose correction' }));
    await waitFor(() => {
      expect(onProposed).toHaveBeenCalled();
    });
    expect(m.proposeCorrection.mock.calls[0]?.[0]).toBe(A_ID);
    expect(m.proposeCorrection.mock.calls[0]?.[1]).toMatchObject({
      parts: [{ hours: '6.00', kind: 'UNEXPLAINED', customer_id: null, reason_id: null }],
      reason: 'Standing idle, no work',
      evidence_attachment_ids: [],
    });
  });
});

describe('allocation detail pages', () => {
  it('shows the superseded history of a corrected entry', async () => {
    m.get.mockImplementation((id) =>
      Promise.resolve(
        id === OLD_ID
          ? entry({ id: OLD_ID, status: 'SUPERSEDED', hours: '9.00', customer_name: 'First Co' })
          : entry({ supersedes_id: OLD_ID, correction_reason: 'Split the day' }),
      ),
    );
    renderWithProviders(
      <Routes>
        <Route
          path={recordRoutePattern('WORK_ALLOCATION')}
          element={<WorkAllocationDetailPage />}
        />
      </Routes>,
      {
        tenantPermissions: ['tenant.meter.read', 'tenant.meter.review'],
        route: recordPath('WORK_ALLOCATION', A_ID),
      },
    );
    const table = await screen.findByRole('table', { name: 'Superseded history' });
    expect(within(table).getByText('Earlier entry')).toBeInTheDocument();
    expect(within(table).getByText('Superseded')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Propose correction' })).toBeEnabled();
  });

  it('disables Decide on your own correction and explains why', async () => {
    m.getCorrection.mockResolvedValue(correction());
    renderWithProviders(
      <Routes>
        <Route
          path={recordRoutePattern('WORK_ALLOCATION_CORRECTION')}
          element={<AllocationCorrectionDetailPage />}
        />
      </Routes>,
      {
        tenantPermissions: ['tenant.meter.read', 'tenant.meter.approve'],
        route: recordPath('WORK_ALLOCATION_CORRECTION', GROUP),
      },
    );
    const decide = await screen.findByRole('button', { name: 'Decide' });
    expect(decide).toBeDisabled();
    expect(screen.getByText(/Someone else must decide your own request/)).toBeInTheDocument();
    expect(m.getCorrection).toHaveBeenCalledWith(GROUP, expect.any(AbortSignal));
  });

  it('decides another person’s correction', async () => {
    const user = userEvent.setup();
    const others = correction();
    const first = others.entries[0];
    if (first === undefined) throw new Error('fixture has no entry');
    others.entries = [{ ...first, recorded_by: OTHER }];
    m.getCorrection.mockResolvedValue(others);
    m.decideCorrection.mockResolvedValue({ ...others, status: 'ACTIVE' });
    renderWithProviders(
      <Routes>
        <Route
          path={recordRoutePattern('WORK_ALLOCATION_CORRECTION')}
          element={<AllocationCorrectionDetailPage />}
        />
      </Routes>,
      {
        tenantPermissions: ['tenant.meter.read', 'tenant.meter.approve'],
        route: recordPath('WORK_ALLOCATION_CORRECTION', GROUP),
      },
    );
    await user.click(await screen.findByRole('button', { name: 'Decide' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.mouseDown(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Approve' }));
    await user.type(within(dialog).getByRole('textbox', { name: /Note/ }), 'Checked the log');
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(m.decideCorrection).toHaveBeenCalled();
    });
    expect(m.decideCorrection.mock.calls[0]?.slice(0, 2)).toEqual([
      GROUP,
      { decision: 'APPROVE', note: 'Checked the log' },
    ]);
  });
});

describe('notification links', () => {
  it('open the correction and the daily report', () => {
    const at = (kind: string) => notificationTargetPath(null, { kind, record_id: 'r1' });
    expect(at('WORK_ALLOCATION_CORRECTION')).toBe('/tenant/work-allocations/corrections/r1');
    expect(at('DAILY_REPORT')).toBe('/tenant/daily-reports/r1');
  });
});
