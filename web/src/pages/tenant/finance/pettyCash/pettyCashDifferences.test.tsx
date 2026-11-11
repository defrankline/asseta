import { screen, waitFor } from '@testing-library/react';
import { Suspense, type ReactNode } from 'react';
import { Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../../access/permissionCodes';
import type { CashVarianceDto } from '../../../../api/custodyTypes';
import type { custodyService } from '../../../../api/services/custodyService';
import type { pettyCashService } from '../../../../api/services/pettyCashService';
import type { policyService } from '../../../../api/services/policyService';
import { cashRecordRouteElements } from '../../../../routes/cashRoutes';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { PettyCashPage } from './PettyCashPage';
import { makeFund } from './pettyCashFixtures';

const m = vi.hoisted(() => ({
  variances: vi.fn<typeof custodyService.variances>(),
  variance: vi.fn<typeof custodyService.variance>(),
  varianceHistory: vi.fn<typeof custodyService.varianceHistory>(),
  myFunds: vi.fn<typeof pettyCashService.myFunds>(),
  funds: vi.fn<typeof pettyCashService.funds>(),
  effective: vi.fn<typeof policyService.effective>(),
}));
vi.mock('../../../../api/services/custodyService', () => ({ custodyService: m }));
vi.mock('../../../../api/services/pettyCashService', () => ({
  pettyCashService: { myFunds: m.myFunds, funds: m.funds },
}));
vi.mock('../../../../api/services/policyService', () => ({
  policyService: { effective: m.effective },
}));

function makeVariance(o: Partial<CashVarianceDto> = {}): CashVarianceDto {
  return {
    id: 'v-1',
    source_type: 'PETTY_CASH_COUNT',
    source_id: 'count-1',
    staff_member_id: 'staff-1',
    staff_member_name: 'Asha Field',
    counterparty_staff_id: null,
    currency: 'TZS',
    declared_amount: '300000.0000',
    received_amount: '290000.0000',
    amount: '10000.0000',
    kind: 'SHORTFALL',
    case_id: null,
    opened_at: '2026-11-10T08:00:00Z',
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
    petty_cash_fund_id: 'fund-1',
    petty_cash_fund_name: 'Office box',
    ...o,
  };
}

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });
const CASH_OFF = ['CASH_CUSTODY'];

beforeEach(() => {
  vi.clearAllMocks();
  m.variances.mockResolvedValue(page([makeVariance()]));
  m.variance.mockResolvedValue(makeVariance());
  m.varianceHistory.mockResolvedValue([]);
  m.myFunds.mockResolvedValue([]);
  m.funds.mockResolvedValue(page([makeFund()]));
  m.effective.mockResolvedValue({
    policy_type: 'PETTY_CASH',
    version_stamp: 'v1',
    values: { enabled: true },
  });
});

describe('petty cash differences with cash custody off', () => {
  it('lists only petty cash differences on the Differences tab', async () => {
    renderWithProviders(<PettyCashPage />, {
      tenantPermissions: [P.tenantPettyCashRead, P.tenantFinanceRead],
      disabledCapabilities: CASH_OFF,
      route: '/tenant/finance/petty-cash?tab=differences',
    });
    expect(await screen.findByText('Office box')).toBeInTheDocument();
    expect(screen.getByText('Petty cash count')).toBeInTheDocument();
    await waitFor(() => {
      expect(m.variances.mock.calls[0]?.[0].filters).toMatchObject({ petty_cash_only: 'true' });
    });
  });

  it('opens the variance record with its follow-up actions', async () => {
    const pass = (_p: string | readonly string[], page: ReactNode) => (
      <Suspense fallback="loading">{page}</Suspense>
    );
    renderWithProviders(<Routes>{cashRecordRouteElements(pass, pass)}</Routes>, {
      tenantPermissions: [P.tenantFinanceRead, P.tenantFinanceVariance, P.tenantPettyCashRead],
      disabledCapabilities: CASH_OFF,
      route: '/tenant/finance/cash/variances/v-1',
    });
    expect(await screen.findByText(/Petty cash difference · Asha Field/)).toBeInTheDocument();
    expect(screen.queryByText(/is not enabled for your company/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Explain' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Petty cash differences/ })).toHaveAttribute(
      'href',
      '/tenant/finance/petty-cash?tab=differences',
    );
    expect(screen.getByRole('link', { name: 'Office box' })).toHaveAttribute(
      'href',
      '/tenant/finance/petty-cash/funds/fund-1',
    );
  });

  it('still says "not enabled" when both cash custody and petty cash are off', async () => {
    const pass = (_p: string | readonly string[], page: ReactNode) => (
      <Suspense fallback="loading">{page}</Suspense>
    );
    renderWithProviders(<Routes>{cashRecordRouteElements(pass, pass)}</Routes>, {
      tenantPermissions: [P.tenantFinanceRead],
      disabledCapabilities: ['CASH_CUSTODY', 'PETTY_CASH'],
      route: '/tenant/finance/cash/variances/v-1',
    });
    expect(await screen.findByText(/is not enabled for your company/)).toBeInTheDocument();
    expect(m.variance).not.toHaveBeenCalled();
  });
});
