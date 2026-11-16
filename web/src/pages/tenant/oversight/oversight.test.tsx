import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CAPABILITY, pathCapability } from '../../../access/capabilities';
import type {
  IdleMachineDto,
  ScorecardDetailDto,
  ScorecardRowDto,
} from '../../../api/oversightTypes';
import {
  idleMachineSchema,
  scorecardDetailSchema,
  type oversightService,
} from '../../../api/services/oversightService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { IdleMachinesPage } from './IdleMachinesPage';
import { ScorecardPage } from './ScorecardPage';
import { ScorecardPersonPage } from './ScorecardPersonPage';

const mocks = vi.hoisted(() => ({
  listScorecard: vi.fn<typeof oversightService.listScorecard>(),
  getScorecard: vi.fn<typeof oversightService.getScorecard>(),
  listIdleMachines: vi.fn<typeof oversightService.listIdleMachines>(),
}));
vi.mock('../../../api/services/oversightService', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  oversightService: {
    listScorecard: mocks.listScorecard,
    getScorecard: mocks.getScorecard,
    listIdleMachines: mocks.listIdleMachines,
  },
}));

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });

const ROW: ScorecardRowDto = {
  staff_member_id: 's1',
  staff_member_name: 'Asha Mollel',
  staff_kind: 'SUPERVISOR',
  employee_code: 'E-07',
  is_active: true,
  day_from: '2026-10-01',
  day_to: '2026-10-26',
  machines: 2,
  daily_reports_missing: 1,
  daily_reports_late: 2,
  unexplained_hours: '3.5',
  unexplained_items: 1,
  alerts: 4,
  alerts_open: 1,
  alerts_acknowledged: 3,
  avg_hours_to_acknowledge: '2.0',
  max_hours_to_acknowledge: '5.0',
  cash_held: [
    { currency: 'TZS', amount: '150000', held_since: '2026-10-20T08:00:00Z', held_days: 6 },
  ],
  cash_held_too_long: 1,
  cash_differences: 2,
  cash_difference_totals: [{ currency: 'TZS', count: 2, amount: '40000' }],
  cash_differences_near_threshold: 1,
  refused_attempts: 0,
  pattern_signals: 1,
  items_total: 12,
};

const DETAIL: ScorecardDetailDto = {
  row: ROW,
  records: [
    {
      item: 'UNEXPLAINED_HOURS',
      record_type: 'engine_interval',
      record_id: null,
      at: '2026-10-22T10:00:00Z',
      day: '2026-10-22',
      machine_id: 'm1',
      machine_code: 'EX-01',
      machine_name: 'Excavator',
      hours: '3.5',
      near_threshold: false,
      detail: {},
    },
    {
      item: 'CASH_DIFFERENCE',
      record_type: 'cash_variance',
      record_id: 'v1',
      at: '2026-10-21T10:00:00Z',
      day: '2026-10-21',
      currency: 'TZS',
      amount: '38000',
      status: 'OPEN',
      near_threshold: true,
      detail: {},
    },
    {
      item: 'PATTERN_SIGNAL',
      record_type: 'risk_signal',
      record_id: 'sig1',
      at: '2026-10-23T10:00:00Z',
      day: null,
      near_threshold: false,
      detail: { case_id: 'case1' },
    },
  ],
};

const IDLE: IdleMachineDto = {
  machine_id: 'm3',
  machine_code: 'GR-02',
  machine_name: 'Grader',
  category_id: null,
  idle_since: '2026-10-01T00:00:00Z',
  idle_days: 25,
  last_engine_activity_at: null,
  last_machine_report_id: null,
  last_machine_report_number: null,
};

const SCORECARD_PERMS = ['tenant.oversight.scorecard.read'];
const OVERSIGHT_PERMS = ['tenant.oversight.read'];

beforeEach(() => {
  mocks.listScorecard.mockResolvedValue(page([ROW]));
  mocks.getScorecard.mockResolvedValue(DETAIL);
  mocks.listIdleMachines.mockResolvedValue(page([IDLE]));
});

describe('oversight contract schemas', () => {
  it('accept the server payloads', () => {
    expect(scorecardDetailSchema.validateSync(DETAIL).records).toHaveLength(3);
    expect(idleMachineSchema.validateSync(IDLE).idle_days).toBe(25);
  });

  it('assigns each page to its capability', () => {
    expect(pathCapability('/tenant/scorecard/s1')).toBe(CAPABILITY.scorecard);
    expect(pathCapability('/tenant/idle-machines')).toBe(CAPABILITY.idleMachines);
  });
});

describe('People scorecard', () => {
  it('lists people with the period from the link and opens a person for the same period', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <Routes>
        <Route path="/tenant/scorecard" element={<ScorecardPage />} />
        <Route path="/tenant/scorecard/:staffId" element={<div>person page</div>} />
      </Routes>,
      {
        tenantPermissions: SCORECARD_PERMS,
        route: '/tenant/scorecard?day_from=2026-10-01&day_to=2026-10-26',
      },
    );
    expect(await screen.findByText('Asha Mollel')).toBeInTheDocument();
    expect(mocks.listScorecard.mock.calls[0]?.[0].filters).toMatchObject({
      day_from: '2026-10-01',
      day_to: '2026-10-26',
    });
    expect(screen.getByText('1 just under the case threshold')).toBeInTheDocument();
    await user.click(screen.getByText('Asha Mollel'));
    expect(await screen.findByText('person page')).toBeInTheDocument();
  });

  it('groups a person’s records by item, each linking to its own page', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/tenant/scorecard/:staffId" element={<ScorecardPersonPage />} />
      </Routes>,
      { tenantPermissions: SCORECARD_PERMS, route: '/tenant/scorecard/s1?day_from=2026-10-01' },
    );
    const hours = await screen.findByRole('region', { name: 'Unexplained engine hours (1)' });
    expect(within(hours).getByRole('link', { name: 'Open engine-hour ledger' })).toHaveAttribute(
      'href',
      '/tenant/engine-hours/machines/m1',
    );
    const cash = screen.getByRole('region', { name: 'Cash differences (1)' });
    expect(within(cash).getByRole('link', { name: 'Open difference' })).toHaveAttribute(
      'href',
      '/tenant/finance/cash/variances/v1',
    );
    expect(within(cash).getByText('Just under the case threshold')).toBeInTheDocument();
    const repeats = screen.getByRole('region', { name: 'Repeated items raised for review (1)' });
    expect(within(repeats).getByRole('link', { name: 'Open investigation' })).toHaveAttribute(
      'href',
      '/tenant/cases/case1',
    );
    expect(mocks.getScorecard).toHaveBeenCalledWith(
      's1',
      { day_from: '2026-10-01', day_to: undefined, item: undefined },
      expect.anything(),
    );
  });

  it('drops links into a capability the company switched off', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/tenant/scorecard/:staffId" element={<ScorecardPersonPage />} />
      </Routes>,
      {
        tenantPermissions: SCORECARD_PERMS,
        route: '/tenant/scorecard/s1',
        disabledCapabilities: ['ENGINE_HOURS'],
      },
    );
    const hours = await screen.findByRole('region', { name: 'Unexplained engine hours (1)' });
    expect(within(hours).queryByRole('link')).toBeNull();
  });
});

describe('Idle machines', () => {
  it('links to the machine', async () => {
    renderWithProviders(<IdleMachinesPage />, { tenantPermissions: OVERSIGHT_PERMS });
    expect(await screen.findByRole('link', { name: 'GR-02 · Grader' })).toHaveAttribute(
      'href',
      '/tenant/machines/m3',
    );
    expect(screen.queryByText('Planned job')).toBeNull();
  });
});
