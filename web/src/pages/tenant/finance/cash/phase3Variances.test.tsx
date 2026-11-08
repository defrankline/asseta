import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../../access/permissionCodes';
import type { CashVarianceDto, VarianceAssigneeDto } from '../../../../api/custodyTypes';
import type { custodyService } from '../../../../api/services/custodyService';
import type { policyService } from '../../../../api/services/policyService';
import { recordPath, recordRoutePattern } from '../../../../navigation/recordRoutes';
import { makeHandover, ME, OTHER_USER, page } from '../../../../test/financeFixtures';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { CashRemittanceDetailPage, CashVarianceDetailPage } from './CashRecordPages';
import { OWN_REQUEST_TOOLTIP } from './custodyDisplay';
import { VariancesTab } from './VariancesTab';

const m = vi.hoisted(() => ({
  variances: vi.fn<typeof custodyService.variances>(),
  handover: vi.fn<typeof custodyService.handover>(),
  decidePartialReason: vi.fn<typeof custodyService.decidePartialReason>(),
  variance: vi.fn<typeof custodyService.variance>(),
  varianceHistory: vi.fn<typeof custodyService.varianceHistory>(),
  varianceAssignees: vi.fn<typeof custodyService.varianceAssignees>(),
  resolveVariance: vi.fn<typeof custodyService.resolveVariance>(),
  decideClosure: vi.fn<typeof custodyService.decideClosure>(),
  custodians: vi.fn<typeof custodyService.custodians>(),
  reasons: vi.fn<typeof custodyService.reasons>(),
  reason: vi.fn<typeof custodyService.reason>(),
  effective: vi.fn<typeof policyService.effective>(),
}));
vi.mock('../../../../api/services/custodyService', () => ({ custodyService: m }));
vi.mock('../../../../api/services/policyService', () => ({
  policyService: { effective: m.effective },
}));

const ASSIGNEE: VarianceAssigneeDto = {
  user_id: OTHER_USER,
  display_name: 'Asha Auditor',
  email: null,
};

const HOURS_VARIANCE = {
  id: 'vvvvvvvv-0000-4000-8000-000000000009',
  source_type: 'CUSTOMER_HOUR',
  source_id: 'ssssssss-0000-4000-8000-000000000001',
  staff_member_id: null,
  counterparty_staff_id: null,
  currency: 'TZS',
  declared_amount: '10.0000',
  received_amount: '12.5000',
  amount: '-2.5000',
  kind: 'SURPLUS',
  case_id: null,
  opened_at: '2026-10-21T16:00:00Z',
  opened_by: null,
  status: 'OPEN',
  reason_id: null,
  proposed_by: null,
  proposed_at: null,
  proposal_note: null,
  outcome: null,
  resolved_by: null,
  resolved_at: null,
  resolution_note: null,
  unit: 'HOURS',
  check_code: 'CONSUMPTION_MISMATCH',
  customer_name: 'Acme Builders',
  assignee_user_id: OTHER_USER,
  assignee_user_name: 'Asha Auditor',
  purchase_id: 'pppppppp-0000-4000-8000-000000000001',
  purchase_number: 'HP-2026-00007',
  job_id: 'jjjjjjjj-0000-4000-8000-000000000001',
  job_number: 'JOB-41',
  evidence_attachment_ids: [],
} as CashVarianceDto;

const policy = (values: Record<string, unknown>) =>
  ({ values }) as Awaited<ReturnType<typeof policyService.effective>>;

function openVariance(variance: CashVarianceDto, permissions: string[]) {
  m.variance.mockResolvedValue(variance);
  renderWithProviders(
    <Routes>
      <Route path={recordRoutePattern('CASH_VARIANCE')} element={<CashVarianceDetailPage />} />
    </Routes>,
    { tenantPermissions: permissions, route: recordPath('CASH_VARIANCE', variance.id) },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  m.effective.mockResolvedValue(policy({}));
  m.variances.mockResolvedValue(page([HOURS_VARIANCE]));
  m.varianceHistory.mockResolvedValue([]);
  m.varianceAssignees.mockResolvedValue([ASSIGNEE]);
  m.custodians.mockResolvedValue(page([]));
  m.reasons.mockResolvedValue(page([]));
});

describe('variances list', () => {
  it('shows hours in hours, who it is assigned to, and filters by assignee', async () => {
    const user = userEvent.setup();
    renderWithProviders(<VariancesTab timeZone="UTC" />, {
      tenantPermissions: [P.tenantFinanceRead, P.tenantFinanceVariance],
    });
    expect((await screen.findAllByText('Asha Auditor')).length).toBeGreaterThan(0);
    expect(screen.getByText('Acme Builders')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /variance of Acme/ })).toBeInTheDocument();
    await user.type(screen.getByRole('combobox', { name: 'Assigned to' }), 'Asha');
    await user.click(await screen.findByRole('option', { name: 'Asha Auditor' }));
    await waitFor(() => {
      expect(m.variances.mock.lastCall?.[0].filters).toMatchObject({
        assignee_user_id: OTHER_USER,
      });
    });
  });
});

describe('variance detail', () => {
  it('links a customer-hour variance to its purchase and its job', async () => {
    openVariance(HOURS_VARIANCE, [P.tenantFinanceRead]);
    expect(await screen.findByRole('link', { name: 'HP-2026-00007' })).toHaveAttribute(
      'href',
      '/tenant/hours/purchases/pppppppp-0000-4000-8000-000000000001',
    );
    expect(screen.getByRole('link', { name: 'JOB-41' })).toBeInTheDocument();
    expect(screen.getByText('Hours used differ from the job’s record')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Customer hours variance · Acme Builders' }),
    ).toBeInTheDocument();
  });

  it('shows the investigation history in order', async () => {
    m.varianceHistory.mockResolvedValue([
      {
        id: 'e1',
        action: 'OPENED',
        actor_user_id: null,
        note: null,
        data: {},
        occurred_at: '2026-10-21T16:00:00Z',
      },
      {
        id: 'e2',
        action: 'CLOSURE_PROPOSED',
        actor_user_id: OTHER_USER,
        actor_user_name: 'Asha Auditor',
        note: 'Meter misread',
        data: {},
        occurred_at: '2026-10-22T09:00:00Z',
      },
    ]);
    openVariance(HOURS_VARIANCE, [P.tenantFinanceRead]);
    const list = await screen.findByRole('list', { name: 'History' });
    expect(within(list).getByText('Opened')).toBeInTheDocument();
    expect(await within(list).findByText('Closure proposed')).toBeInTheDocument();
    expect(within(list).getByText(/Meter misread/)).toBeInTheDocument();
  });

  it('refuses to propose a closure without evidence when the policy needs it', async () => {
    const user = userEvent.setup();
    m.effective.mockResolvedValue(
      policy({ variance_evidence_required: true, variance_closure_requires_second_person: true }),
    );
    openVariance(HOURS_VARIANCE, [
      P.tenantFinanceRead,
      P.tenantFinanceVariance,
      P.tenantPolicyRead,
    ]);
    await user.click(await screen.findByRole('button', { name: 'Propose closure' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Outcome/ }));
    await user.click(await screen.findByRole('option', { name: 'Explained' }));
    await user.type(
      within(dialog).getByRole('textbox', { name: /Explanation/ }),
      'Double entry on the ledger',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Propose closure' }));
    expect(await within(dialog).findByText('Attach the supporting evidence')).toBeInTheDocument();
    expect(m.resolveVariance).not.toHaveBeenCalled();
  });

  it('offers only explained or corrected for hours', async () => {
    const user = userEvent.setup();
    openVariance(HOURS_VARIANCE, [P.tenantFinanceRead, P.tenantFinanceVariance]);
    await user.click(await screen.findByRole('button', { name: 'Propose closure' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Outcome/ }));
    expect(await screen.findByRole('option', { name: 'Explained' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Corrected error' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Recovered' })).not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Written off' })).not.toBeInTheDocument();
  });

  const proposed = {
    ...HOURS_VARIANCE,
    status: 'CLOSURE_PROPOSED',
    proposed_by: OTHER_USER,
    proposed_by_name: 'Asha Auditor',
    proposed_at: '2026-10-22T09:00:00Z',
    proposal_note: 'Meter misread',
    proposed_outcome: 'EXPLAINED',
  } as CashVarianceDto;

  it('lets a second person decide the closure', async () => {
    const user = userEvent.setup();
    m.decideClosure.mockResolvedValue({ ...proposed, status: 'RESOLVED' });
    openVariance(proposed, [P.tenantFinanceRead, P.tenantFinanceVarianceClose]);
    await user.click(await screen.findByRole('button', { name: 'Decide closure' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Approve' }));
    await user.click(within(dialog).getByRole('button', { name: /Record decision|Approve/ }));
    await waitFor(() => {
      expect(m.decideClosure).toHaveBeenCalledWith(
        proposed.id,
        expect.objectContaining({ approve: true }),
        expect.any(String),
      );
    });
  });

  it('disables deciding a closure you proposed, with the tooltip', async () => {
    openVariance({ ...proposed, proposed_by: ME, proposed_by_name: 'Me' }, [
      P.tenantFinanceRead,
      P.tenantFinanceVarianceClose,
    ]);
    const button = await screen.findByRole('button', {
      name: new RegExp(OWN_REQUEST_TOOLTIP),
    });
    expect(button).toBeDisabled();
  });
});

describe('remittance detail', () => {
  const PARTIAL = {
    id: 'a1',
    status: 'PENDING',
    reason_id: null,
    reason: 'Kept for fuel',
    created_by: OTHER_USER,
    created_at: '2026-10-21T15:00:00Z',
    decided_by: null,
    decided_at: null,
    decision_note: null,
  } as const;

  function openRemittance(partialBy: string) {
    m.handover.mockResolvedValue(
      makeHandover({
        remittance_number: 'RMT-2026-000031',
        evidence_status: 'SUPPORTED',
        partial_approval: { ...PARTIAL, created_by: partialBy },
      }),
    );
    renderWithProviders(
      <Routes>
        <Route
          path={recordRoutePattern('CASH_REMITTANCE')}
          element={<CashRemittanceDetailPage />}
        />
      </Routes>,
      {
        tenantPermissions: [P.tenantFinanceRead, P.tenantFinanceRetentionApprove],
        route: recordPath('CASH_REMITTANCE', makeHandover().id),
      },
    );
  }

  it('shows the number, the evidence status and lets a second person decide the reason', async () => {
    const user = userEvent.setup();
    m.decidePartialReason.mockResolvedValue(makeHandover());
    openRemittance(OTHER_USER);
    expect(await screen.findByRole('heading', { name: /RMT-2026-000031/ })).toBeInTheDocument();
    expect(screen.getByText('Supported')).toBeInTheDocument();
    expect(screen.getAllByText('Kept for fuel').length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: 'Decide partial reason' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Reject' }));
    await user.type(within(dialog).getByRole('textbox', { name: /Note/ }), 'Not agreed');
    await user.click(within(dialog).getByRole('button', { name: /Record decision|Reject/ }));
    await waitFor(() => {
      expect(m.decidePartialReason).toHaveBeenCalledWith(
        makeHandover().id,
        expect.objectContaining({ approve: false, note: 'Not agreed' }),
        expect.any(String),
      );
    });
  });

  it('disables deciding your own partial reason', async () => {
    openRemittance(ME);
    expect(
      await screen.findByRole('button', { name: new RegExp(OWN_REQUEST_TOOLTIP) }),
    ).toBeDisabled();
  });
});
