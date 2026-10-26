import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { revenueService } from '../../../api/services/revenueService';
import { recordPath, recordRoutePattern } from '../../../navigation/recordRoutes';
import { JOB_ID, ME_ID } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import {
  ACTIVITY_ID,
  APPROVAL_ID,
  CASE_ID,
  DIFFERENCE_ID,
  INVOICE_ID,
  makeActivity,
  makeApproval,
  makeDifference,
  OTHER_ID,
  page,
  REVENUE_REASON,
} from '../../../test/revenueFixtures';
import { NonRevenuePage } from './NonRevenuePage';
import { RevenueDifferencesPage } from './RevenueDifferencesPage';
import { RevenueReasonsPage } from './RevenueReasonsPage';
import { NonRevenueApprovalDetailPage, RevenueDifferenceDetailPage } from './RevenueRecordPages';

const mocks = vi.hoisted(() => ({
  listDifferences: vi.fn<typeof revenueService.listDifferences>(),
  getDifference: vi.fn<typeof revenueService.getDifference>(),
  explainDifference: vi.fn<typeof revenueService.explainDifference>(),
  decideDifference: vi.fn<typeof revenueService.decideDifference>(),
  listReasons: vi.fn<typeof revenueService.listReasons>(),
  getReason: vi.fn<typeof revenueService.getReason>(),
  createReason: vi.fn<typeof revenueService.createReason>(),
  updateReason: vi.fn<typeof revenueService.updateReason>(),
  deactivateReason: vi.fn<typeof revenueService.deactivateReason>(),
  reactivateReason: vi.fn<typeof revenueService.reactivateReason>(),
  listActivities: vi.fn<typeof revenueService.listActivities>(),
  listApprovals: vi.fn<typeof revenueService.listApprovals>(),
  getApproval: vi.fn<typeof revenueService.getApproval>(),
  proposeApproval: vi.fn<typeof revenueService.proposeApproval>(),
  decideApproval: vi.fn<typeof revenueService.decideApproval>(),
}));
vi.mock('../../../api/services/revenueService', () => ({ revenueService: mocks }));
vi.mock('../../../api/services/machineService', () => ({
  machineService: { list: vi.fn(), get: vi.fn() },
}));

const READ = 'tenant.revenue.read';
const EXPLAIN = 'tenant.revenue.explain';
const DECIDE = 'tenant.revenue.decide';

beforeEach(() => {
  mocks.listReasons.mockResolvedValue(page([REVENUE_REASON]));
  mocks.getReason.mockResolvedValue(REVENUE_REASON);
});

function renderDifference(permissions: string[]) {
  return renderWithProviders(
    <Routes>
      <Route
        path={recordRoutePattern('REVENUE_DIFFERENCE')}
        element={<RevenueDifferenceDetailPage />}
      />
    </Routes>,
    { tenantPermissions: permissions, route: recordPath('REVENUE_DIFFERENCE', DIFFERENCE_ID) },
  );
}

describe('Revenue differences', () => {
  it('lists differences per currency with the status filter defaulting to "to explain"', async () => {
    mocks.listDifferences.mockResolvedValue(page([makeDifference()]));
    renderWithProviders(<RevenueDifferencesPage />, { tenantPermissions: [READ] });
    const table = await screen.findByRole('table');
    expect(within(table).getByText('EX-01 · Excavator')).toBeInTheDocument();
    expect(within(table).getByText('Day 2026-10-20')).toBeInTheDocument();
    expect(within(table).getByText('To explain')).toBeInTheDocument();
    expect(within(table).getByText(/200,000/)).toBeInTheDocument();
    expect(mocks.listDifferences).toHaveBeenCalledWith(
      expect.objectContaining({ filters: { status: 'OPEN' } }),
      expect.any(AbortSignal),
    );
  });

  it('shows jobs and money sources with links, and explains with a reason', async () => {
    const user = userEvent.setup();
    mocks.getDifference.mockResolvedValue(makeDifference());
    mocks.explainDifference.mockResolvedValue(
      makeDifference({
        status: 'EXPLANATION_PROPOSED',
        reason_id: REVENUE_REASON.id,
        explained_by: ME_ID,
      }),
    );
    renderDifference([READ, EXPLAIN]);
    expect(
      await screen.findByRole('heading', { name: 'Difference · EX-01 · Excavator' }),
    ).toBeInTheDocument();
    const jobs = screen.getByRole('table', { name: 'Jobs' });
    expect(within(jobs).getByRole('link', { name: 'J-100' })).toHaveAttribute(
      'href',
      `/tenant/jobs/${JOB_ID}`,
    );
    const sources = screen.getByRole('table', { name: 'Money sources' });
    expect(within(sources).getByRole('link', { name: 'Open invoice' })).toHaveAttribute(
      'href',
      `/tenant/finance/invoices/${INVOICE_ID}`,
    );
    expect(screen.getByRole('link', { name: 'Daily sheet' })).toHaveAttribute(
      'href',
      expect.stringContaining('/tenant/engine-hours/daily-sheet/'),
    );
    // No decide permission: only Explain is offered.
    expect(screen.queryByRole('button', { name: /Confirm difference/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Explain' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Reason/ }));
    await user.click(await screen.findByRole('option', { name: 'MOVE · Movement between sites' }));
    await user.type(
      within(dialog).getByRole('textbox', { name: /What happened/ }),
      'Machine moved to site B',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Propose explanation' }));
    await waitFor(() => {
      expect(mocks.explainDifference).toHaveBeenCalledWith(
        DIFFERENCE_ID,
        { reason_id: REVENUE_REASON.id, note: 'Machine moved to site B' },
        expect.any(String),
      );
    });
    expect(
      await screen.findByText('Explanation proposed; someone else decides it.'),
    ).toBeInTheDocument();
  });

  it('disables Decide on your own explanation with the reason', async () => {
    mocks.getDifference.mockResolvedValue(
      makeDifference({
        status: 'EXPLANATION_PROPOSED',
        reason_id: REVENUE_REASON.id,
        reason_name: REVENUE_REASON.name,
        explanation_note: 'Moved',
        explained_by: ME_ID,
        explained_by_name: 'Me',
        explained_at: '2026-10-21T08:00:00Z',
      }),
    );
    renderDifference([READ, EXPLAIN, DECIDE]);
    expect(await screen.findByRole('button', { name: 'Decide' })).toBeDisabled();
    expect(screen.getByText(/Someone else must decide your own request/)).toBeInTheDocument();
  });

  it("decides someone else's explanation and shows the case and adjustments", async () => {
    const user = userEvent.setup();
    const proposed = makeDifference({
      status: 'EXPLANATION_PROPOSED',
      reason_id: REVENUE_REASON.id,
      reason_name: REVENUE_REASON.name,
      explanation_note: 'Moved',
      explained_by: OTHER_ID,
      explained_by_name: 'Asha Mwita',
      explained_at: '2026-10-21T08:00:00Z',
      case_id: CASE_ID,
      case_number: 'CASE-7',
      adjustments: [
        {
          id: 'ffffffff-0000-4000-8000-0000000000e1',
          previous_difference: '250000.0000',
          new_difference: '200000.0000',
          amount: '-50000.0000',
          cause_type: 'non_revenue_approval',
          cause_id: APPROVAL_ID,
          created_by: null,
          created_at: '2026-10-21T09:00:00Z',
        },
      ],
      adjusted_difference: '150000.0000',
    });
    mocks.getDifference.mockResolvedValue(proposed);
    mocks.decideDifference.mockResolvedValue({ ...proposed, status: 'EXPLAINED' });
    renderDifference([READ, DECIDE]);
    expect(await screen.findByRole('link', { name: 'CASE-7' })).toHaveAttribute(
      'href',
      `/tenant/cases/${CASE_ID}`,
    );
    const adjustments = screen.getByRole('table', { name: 'Adjustments' });
    expect(
      within(adjustments).getByRole('link', { name: 'Non-revenue time approved' }),
    ).toHaveAttribute('href', `/tenant/non-revenue-approvals/${APPROVAL_ID}`);
    await user.click(screen.getByRole('button', { name: 'Decide' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Approve the explanation' }));
    await user.type(within(dialog).getByRole('textbox', { name: /Note/ }), 'Checked the log');
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(mocks.decideDifference).toHaveBeenCalledWith(
        DIFFERENCE_ID,
        { decision: 'APPROVE', note: 'Checked the log' },
        expect.any(String),
      );
    });
  });

  it('offers only "Confirm difference" on an open difference', async () => {
    const user = userEvent.setup();
    mocks.getDifference.mockResolvedValue(makeDifference());
    mocks.decideDifference.mockResolvedValue(makeDifference({ status: 'CONFIRMED' }));
    renderDifference([READ, DECIDE]);
    await user.click(await screen.findByRole('button', { name: 'Confirm difference' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /Note/ }), 'Customer will pay');
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(mocks.decideDifference).toHaveBeenCalledWith(
        DIFFERENCE_ID,
        { decision: 'CONFIRM', note: 'Customer will pay' },
        expect.any(String),
      );
    });
  });
});

describe('Non-revenue hours', () => {
  it('lists time awaiting explanation and explains it with a reason', async () => {
    const user = userEvent.setup();
    mocks.listActivities.mockResolvedValue(page([makeActivity()]));
    mocks.proposeApproval.mockResolvedValue(makeApproval());
    renderWithProviders(<NonRevenuePage />, { tenantPermissions: [READ, EXPLAIN] });
    const table = await screen.findByRole('table');
    expect(within(table).getByText('Movement (mobilization)')).toBeInTheDocument();
    expect(within(table).getByText('Counts as revenue (not explained)')).toBeInTheDocument();
    expect(mocks.listActivities).toHaveBeenCalledWith(
      expect.objectContaining({ filters: { status: 'NONE' } }),
      expect.any(AbortSignal),
    );
    await user.click(within(table).getByRole('button', { name: 'Explain' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Reason/ }));
    await user.click(await screen.findByRole('option', { name: 'MOVE · Movement between sites' }));
    await user.click(within(dialog).getByRole('button', { name: 'Propose explanation' }));
    await waitFor(() => {
      expect(mocks.proposeApproval).toHaveBeenCalledWith(
        { activity_id: ACTIVITY_ID, reason_id: REVENUE_REASON.id, note: 'Drove to site B' },
        expect.any(String),
      );
    });
  });

  it('hides Explain without the explain permission', async () => {
    mocks.listActivities.mockResolvedValue(page([makeActivity()]));
    renderWithProviders(<NonRevenuePage />, { tenantPermissions: [READ] });
    await screen.findByRole('table');
    expect(screen.queryByRole('button', { name: 'Explain' })).not.toBeInTheDocument();
  });

  it('lists approvals; your own explanation cannot be decided', async () => {
    mocks.listApprovals.mockResolvedValue(page([makeApproval()]));
    renderWithProviders(<NonRevenuePage />, {
      tenantPermissions: [READ, DECIDE],
      route: '/tenant/non-revenue-approvals?tab=approvals',
    });
    const table = await screen.findByRole('table');
    expect(within(table).getByText('Awaiting decision')).toBeInTheDocument();
    expect(
      within(table).getByRole('button', {
        name: 'Decide (Someone else must decide your own request)',
      }),
    ).toBeDisabled();
  });

  it("approves someone else's explanation on its detail page", async () => {
    const user = userEvent.setup();
    const proposed = makeApproval({ proposed_by: OTHER_ID, proposed_by_name: 'Asha Mwita' });
    mocks.getApproval.mockResolvedValue(proposed);
    mocks.decideApproval.mockResolvedValue({ ...proposed, status: 'APPROVED' });
    renderWithProviders(
      <Routes>
        <Route
          path={recordRoutePattern('NON_REVENUE_APPROVAL')}
          element={<NonRevenueApprovalDetailPage />}
        />
      </Routes>,
      {
        tenantPermissions: [READ, DECIDE],
        route: recordPath('NON_REVENUE_APPROVAL', APPROVAL_ID),
      },
    );
    expect(
      await screen.findByRole('heading', { name: 'Non-revenue time · 1.50 h · EX-01 · Excavator' }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Decide' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Approve as non-revenue' }));
    await user.type(within(dialog).getByRole('textbox', { name: /Note/ }), 'Log matches GPS');
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(mocks.decideApproval).toHaveBeenCalledWith(
        APPROVAL_ID,
        { decision: 'APPROVE', note: 'Log matches GPS' },
        expect.any(String),
      );
    });
    expect(await screen.findByText('Approved as non-revenue time.')).toBeInTheDocument();
  });
});

describe('Revenue reasons', () => {
  it('creates a reason (decide holders manage the list)', async () => {
    const user = userEvent.setup();
    mocks.createReason.mockResolvedValue(REVENUE_REASON);
    renderWithProviders(<RevenueReasonsPage />, { tenantPermissions: [READ, DECIDE] });
    expect(await screen.findByText('Movement between sites')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'New reason' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /Code/ }), 'MOVE');
    await user.type(
      within(dialog).getByRole('textbox', { name: /^Name/ }),
      'Movement between sites',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Create reason' }));
    await waitFor(() => {
      expect(mocks.createReason).toHaveBeenCalledWith(
        { code: 'MOVE', name: 'Movement between sites', description: null },
        expect.any(String),
      );
    });
  });

  it('deactivates a reason with a reason and the version', async () => {
    const user = userEvent.setup();
    mocks.deactivateReason.mockResolvedValue({ ...REVENUE_REASON, is_active: false });
    renderWithProviders(<RevenueReasonsPage />, { tenantPermissions: [READ, DECIDE] });
    const table = await screen.findByRole('table');
    await user.click(within(table).getByRole('button', { name: /actions/i }));
    await user.click(screen.getByRole('menuitem', { name: /Deactivate/ }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'No longer used');
    await user.click(within(dialog).getByRole('button', { name: /Deactivate/ }));
    await waitFor(() => {
      expect(mocks.deactivateReason).toHaveBeenCalledWith(
        REVENUE_REASON.id,
        { reason: 'No longer used', version: 1 },
        expect.any(String),
      );
    });
  });

  it('is read-only without the decide permission', async () => {
    renderWithProviders(<RevenueReasonsPage />, { tenantPermissions: [READ] });
    expect(await screen.findByText('Movement between sites')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New reason' })).not.toBeInTheDocument();
  });
});
