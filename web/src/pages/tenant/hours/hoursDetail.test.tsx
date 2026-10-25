import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { DiscountDto, TransferDto } from '../../../api/hoursTypes';
import type { discountService, hoursRequestService } from '../../../api/services/hoursService';
import type { policyService } from '../../../api/services/policyService';
import { recordPath, recordRoutePattern } from '../../../navigation/recordRoutes';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { CustomerDiscountDetailPage } from './CustomerDiscountsPage';
import { HoursTransferDetailPage } from './HoursRequestDetailPages';

const ME = '33333333-3333-4333-8333-333333333333';
const OTHER = '44444444-4444-4444-8444-444444444444';

const mocks = vi.hoisted(() => ({
  effective: vi.fn<typeof policyService.effective>(),
  getTransfer: vi.fn<typeof hoursRequestService.getTransfer>(),
  getDiscount: vi.fn<typeof discountService.get>(),
}));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { effective: mocks.effective },
}));
vi.mock('../../../api/services/hoursService', () => ({
  hoursService: {},
  hoursRequestService: { getTransfer: mocks.getTransfer },
  discountService: { get: mocks.getDiscount },
  creditArrangementService: {},
  hoursReasonService: { search: vi.fn(), get: vi.fn() },
}));

const transfer = (over: Partial<TransferDto> = {}): TransferDto => ({
  id: 't1',
  purchase_id: 'p1',
  purchase_number: 'HP-2026-00007',
  customer_name: 'Juma Construction',
  from_machine_id: 'm1',
  from_machine_code: 'EX-01',
  from_machine_name: 'Excavator',
  to_machine_id: 'm2',
  to_machine_code: 'LD-02',
  to_machine_name: 'Loader',
  hours: '2',
  reason: 'Machine down',
  reason_code_id: null,
  client_id: null,
  requested_at: '2026-10-20T08:00:00Z',
  requested_by: OTHER,
  requested_by_name: 'Asha Mwita',
  status: 'PENDING',
  decided_at: null,
  decided_by: null,
  decision_note: null,
  ...over,
});

const discount = (over: Partial<DiscountDto> = {}): DiscountDto => ({
  id: 'd1',
  customer_id: 'c1',
  customer_name: 'Juma Construction',
  percent: '5',
  effective_from: '2026-10-01',
  effective_to: null,
  reason: 'Loyal customer',
  reason_code_id: null,
  proposed_at: '2026-10-20T08:00:00Z',
  proposed_by: ME,
  status: 'PROPOSED',
  decided_at: null,
  decided_by: null,
  decision_note: null,
  revoke_reason: null,
  revoked_at: null,
  revoked_by: null,
  version: 1,
  ...over,
});

beforeEach(() => {
  mocks.effective.mockResolvedValue({
    policy_type: 'CUSTOMER_HOURS',
    version_stamp: 'v1',
    values: { enabled: true, reason_code_required: false },
  });
});

describe('HoursTransferDetailPage', () => {
  const perms = ['tenant.hours.read', 'tenant.hours.transfer_approve'];
  const renderAt = (id: string) =>
    renderWithProviders(
      <Routes>
        <Route path={recordRoutePattern('HOURS_TRANSFER')} element={<HoursTransferDetailPage />} />
      </Routes>,
      { tenantPermissions: perms, route: recordPath('HOURS_TRANSFER', id) },
    );

  it('loads the transfer by id and shows names, status, history and Decide', async () => {
    mocks.getTransfer.mockResolvedValue(
      transfer({
        status: 'APPROVED',
        decided_at: '2026-10-21T09:00:00Z',
        decided_by: ME,
        decided_by_name: 'Me',
        decision_note: 'Checked',
      }),
    );
    renderAt('t1');
    expect(
      await screen.findByRole('heading', {
        name: 'Hours transfer · 2 h · EX-01 · Excavator → LD-02 · Loader',
      }),
    ).toBeInTheDocument();
    expect(mocks.getTransfer).toHaveBeenCalledWith('t1', expect.any(AbortSignal));
    expect(screen.getAllByText('Juma Construction').length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: 'HP-2026-00007' })).toBeInTheDocument();
    expect(screen.getAllByText('Asha Mwita').length).toBeGreaterThan(0);
    const history = screen.getByRole('list', { name: 'History' });
    expect(history).toHaveTextContent('Requested');
    expect(history).toHaveTextContent('Approved');
    // Decided: no command left.
    expect(screen.queryByRole('button', { name: 'Decide' })).not.toBeInTheDocument();
  });

  it('offers Decide on someone else’s pending request', async () => {
    mocks.getTransfer.mockResolvedValue(transfer());
    renderAt('t1');
    expect(await screen.findByRole('button', { name: 'Decide' })).toBeEnabled();
  });
});

describe('CustomerDiscountDetailPage', () => {
  it('disables deciding your own proposal with the explanation', async () => {
    mocks.getDiscount.mockResolvedValue(discount());
    renderWithProviders(
      <Routes>
        <Route
          path={recordRoutePattern('HOURS_DISCOUNT')}
          element={<CustomerDiscountDetailPage />}
        />
      </Routes>,
      {
        tenantPermissions: ['tenant.hours.read', 'tenant.hours.discount_approve'],
        route: recordPath('HOURS_DISCOUNT', 'd1'),
      },
    );
    expect(
      await screen.findByRole('heading', { name: 'Discount for Juma Construction' }),
    ).toBeInTheDocument();
    expect(mocks.getDiscount).toHaveBeenCalledWith('d1', expect.any(AbortSignal));
    expect(screen.getByRole('button', { name: 'Decide' })).toBeDisabled();
    expect(screen.getByText(/Someone else must decide your own request/)).toBeInTheDocument();
  });
});
