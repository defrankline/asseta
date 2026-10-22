import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { insightsService, tenantMlService } from '../../../api/services/insightsService';
import type { peopleService } from '../../../api/services/peopleService';
import { PERSON } from '../../../test/caseFixtures';
import { page } from '../../../test/financeFixtures';
import {
  CASE_ML,
  JOB_ID,
  makeCashFlow,
  makeInsights,
  makeObservation,
  makeOverrideReport,
  makeReadiness,
  makeTenantStatus,
} from '../../../test/mlFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { resetPersonDirectory } from '../shared/personDirectory';
import { InsightsPage } from './InsightsPage';

const mocks = vi.hoisted(() => ({
  get: vi.fn<typeof insightsService.get>(),
  overrides: vi.fn<typeof insightsService.manualOverrides>(),
  status: vi.fn<typeof tenantMlService.status>(),
  observations: vi.fn<typeof tenantMlService.observations>(),
  people: vi.fn<typeof peopleService.list>(),
  search: vi.fn<typeof peopleService.search>(),
}));
vi.mock('../../../api/services/insightsService', () => ({
  insightsService: { get: mocks.get, manualOverrides: mocks.overrides },
  tenantMlService: { status: mocks.status, observations: mocks.observations },
}));
vi.mock('../../../api/services/peopleService', () => ({
  PEOPLE_BATCH: 100,
  peopleService: { list: mocks.people, search: mocks.search },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 }),
  },
}));

const FLEET = [P.tenantFleetRead];
const ALL = [
  P.tenantFleetRead,
  P.tenantSignalRead,
  P.tenantFinanceReport,
  P.tenantMeterRead,
  P.tenantCaseRead,
  P.tenantDirectoryRead,
];

beforeEach(() => {
  resetPersonDirectory();
  mocks.get.mockResolvedValue(makeInsights());
  mocks.status.mockResolvedValue(makeTenantStatus());
  mocks.overrides.mockResolvedValue(makeOverrideReport());
  mocks.observations.mockResolvedValue(page([makeObservation()]));
  mocks.people.mockResolvedValue([PERSON]);
  mocks.search.mockResolvedValue([PERSON]);
});
afterEach(() => {
  vi.clearAllMocks();
});

function renderPage(permissions: string[], route = '/tenant/insights') {
  return renderWithProviders(
    <Routes>
      <Route path="/tenant/insights" element={<InsightsPage />} />
      <Route path="/tenant/cases/:caseId" element={<p>Case page</p>} />
      <Route path="/tenant/jobs/:jobId" element={<p>Job page</p>} />
    </Routes>,
    { tenantPermissions: permissions, route },
  );
}

const NO_SCORE = /score|probabilit|fraud/i;

describe('InsightsPage: model status', () => {
  it('explains NOT_ENOUGH_HISTORY with the reasons and each minimum vs observed', async () => {
    renderPage([...FLEET, P.tenantSignalRead]);
    const card = await screen.findByRole('region', { name: 'Model status' });
    expect(await within(card).findByText('Not enough history yet')).toBeInTheDocument();
    expect(
      within(card).getAllByText(/3 machines with usable history; at least 5 required\./).length,
    ).toBeGreaterThan(0);
    expect(within(card).getByText('Machines with history')).toBeInTheDocument();
    expect(within(card).getByText('3 of 5 needed')).toBeInTheDocument();
    expect(within(card).getByText('40 of 80 needed')).toBeInTheDocument();
    expect(card.textContent).not.toMatch(NO_SCORE);
  });

  it.each([
    ['MODEL_OFF', 'Model off', 'Anomaly models are switched off platform-wide.'],
    ['LEARNING_SHADOW', 'Learning (shadow)', 'A model runs in shadow mode.'],
    ['ACTIVE', 'Active', 'An approved model is active.'],
  ] as const)('shows the %s state as a plain label', async (state, label, summary) => {
    mocks.status.mockResolvedValue(
      makeTenantStatus({
        state,
        label,
        summary,
        readiness: makeReadiness({ status: 'READY', reasons: [] }),
        deployed:
          state === 'MODEL_OFF'
            ? null
            : {
                name: 'm',
                version: 3,
                mode: state === 'ACTIVE' ? 'ACTIVE' : 'SHADOW',
                deployed_at: null,
              },
      }),
    );
    renderPage([...FLEET, P.tenantSignalRead]);
    const card = await screen.findByRole('region', { name: 'Model status' });
    expect(await within(card).findByText(label)).toBeInTheDocument();
    expect(within(card).getByText(summary)).toBeInTheDocument();
    expect(within(card).queryByText('Machines with history')).not.toBeInTheDocument();
    expect(card.textContent).not.toMatch(NO_SCORE);
  });

  it('hides the status card without tenant.signal.read', async () => {
    renderPage(FLEET);
    await screen.findByText('EX-01 · Excavator 1');
    expect(screen.queryByRole('region', { name: 'Model status' })).not.toBeInTheDocument();
    expect(mocks.status).not.toHaveBeenCalled();
  });
});

describe('InsightsPage: baseline insights', () => {
  it('flags fuel rows outside the usual range and explains insufficient rows', async () => {
    renderPage(FLEET);
    const flagged = (await screen.findByText('EX-01 · Excavator 1')).closest('tr') as HTMLElement;
    expect(within(flagged).getByText('Outside usual range')).toBeInTheDocument();
    expect(within(flagged).getByText('18.4')).toBeInTheDocument();
    expect(within(flagged).getByText(/10.5 – 13.8 \(median 12.1\)/)).toBeInTheDocument();
    expect(
      within(flagged).getByRole('img', { name: /usual range 10.5 to 13.8/ }),
    ).toBeInTheDocument();
    const short = screen.getByText('LD-02 · Loader 2').closest('tr') as HTMLElement;
    expect(within(short).getByText('Not enough history')).toBeInTheDocument();
    expect(
      within(short).getByText(
        'Not enough history yet: 2 of 4 weeks observed. Missing: meter hours in 2 more weeks.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/1 of 2 machines outside their usual range/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/fraud/i);
  });

  it('renders utilisation with weekly bars, the trend and insufficient rows', async () => {
    const user = userEvent.setup();
    renderPage(FLEET);
    await user.click(await screen.findByRole('tab', { name: 'Utilisation' }));
    const row = (await screen.findByText('EX-01 · Excavator 1')).closest('tr') as HTMLElement;
    expect(within(row).getByText('6.3')).toBeInTheDocument();
    expect(within(row).getByText('Rising')).toBeInTheDocument();
    expect(within(row).getByText('+1.5 h/week')).toBeInTheDocument();
    expect(
      within(row).getByRole('img', { name: /Weekly hours for EX-01, 2 weeks/ }),
    ).toBeInTheDocument();
    const short = screen.getByText('LD-02 · Loader 2').closest('tr') as HTMLElement;
    expect(
      within(short).getByText(/1 of 4 weeks observed\. Missing: 3 more observed weeks/),
    ).toBeInTheDocument();
  });

  it('hides cash flow without tenant.finance.report', async () => {
    renderPage(FLEET, '/tenant/insights?tab=cash');
    await screen.findByText('EX-01 · Excavator 1');
    expect(screen.queryByRole('tab', { name: 'Cash flow' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Manual overrides' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Model observations' })).not.toBeInTheDocument();
  });

  it('shows weekly cash flow with money and trend when permitted', async () => {
    mocks.get.mockResolvedValue(makeInsights({ cash_flow: makeCashFlow() }));
    renderPage([...FLEET, P.tenantFinanceReport], '/tenant/insights?tab=cash');
    const table = await screen.findByRole('table', { name: 'Weekly cash flow' });
    expect(within(table).getByText(/1,100,000/)).toBeInTheDocument();
    expect(screen.getByText('Rising')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Weekly net cash flow in TZS/ })).toBeInTheDocument();
  });

  it('explains cash flow without enough weeks', async () => {
    mocks.get.mockResolvedValue(
      makeInsights({
        cash_flow: makeCashFlow({
          status: 'INSUFFICIENT_DATA',
          weeks_observed: 3,
          trend: null,
          trend_per_week: null,
          median_weekly_net: null,
          missing: ['3 more complete weeks'],
        }),
      }),
    );
    renderPage([...FLEET, P.tenantFinanceReport], '/tenant/insights?tab=cash');
    expect(
      await screen.findByText(
        'Not enough history yet: 3 of 6 weeks observed. Missing: 3 more complete weeks.',
      ),
    ).toBeInTheDocument();
  });
});

describe('InsightsPage: manual overrides', () => {
  it('shows OCR vs entered values with the summary and a link to the job', async () => {
    const user = userEvent.setup();
    renderPage(ALL, '/tenant/insights?tab=overrides');
    const row = (await screen.findByText('JOB-2026-00042')).closest('tr') as HTMLElement;
    expect(within(row).getByText('1234.5')).toBeInTheDocument();
    expect(within(row).getByText('1243.5')).toBeInTheDocument();
    expect(within(row).getByText('82%')).toBeInTheDocument();
    expect(within(row).getByText('Sam Supervisor')).toBeInTheDocument();
    expect(screen.getByText('Entered value differs from OCR')).toBeInTheDocument();
    const job = within(row).getByRole('link', { name: 'JOB-2026-00042' });
    expect(job).toHaveAttribute('href', `/tenant/jobs/${JOB_ID}`);
    await user.click(job);
    expect(await screen.findByText('Job page')).toBeInTheDocument();
  });

  it('sends period and person filters to the server', async () => {
    const user = userEvent.setup();
    renderPage(ALL, '/tenant/insights?tab=overrides');
    await screen.findByText('JOB-2026-00042');
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-10-01' } });
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-10-07' } });
    await waitFor(() => {
      const f = mocks.overrides.mock.lastCall?.[0].filters;
      expect(f?.captured_from).toBeDefined();
      expect(f?.captured_to).toBeDefined();
    });
    const f = mocks.overrides.mock.lastCall?.[0].filters;
    expect(Date.parse(f?.captured_to ?? '') - Date.parse(f?.captured_from ?? '')).toBe(
      7 * 24 * 3600 * 1000,
    );
    const person = screen.getByRole('combobox', { name: 'Entered by' });
    await user.click(person);
    await user.type(person, 'rit');
    await waitFor(() => {
      expect(mocks.search).toHaveBeenCalledWith('rit', expect.any(AbortSignal));
    });
    await user.click(await screen.findByRole('option', { name: 'Rita Reviewer' }));
    await waitFor(() => {
      expect(mocks.overrides.mock.lastCall?.[0].filters?.user_id).toBe(PERSON.user_id);
    });
  });
});

describe('InsightsPage: model observations', () => {
  it('shows neutral observations with a case link and never a score', async () => {
    const user = userEvent.setup();
    renderPage(ALL, '/tenant/insights?tab=observations');
    expect(
      await screen.findByText('Fuel per meter hour well above this machine’s usual weeks.'),
    ).toBeInTheDocument();
    expect(screen.getByText(/They are not a conclusion about any person/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(NO_SCORE);
    const link = screen.getByRole('link', { name: 'Open case' });
    expect(link).toHaveAttribute('href', `/tenant/cases/${CASE_ML}`);
    await user.click(link);
    expect(await screen.findByText('Case page')).toBeInTheDocument();
  });
});
