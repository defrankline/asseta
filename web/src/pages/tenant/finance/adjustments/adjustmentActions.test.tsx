import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../../access/permissionCodes';
import type { AdjustmentRequestDto } from '../../../../api/adjustmentTypes';
import type { HoursPurchaseDto } from '../../../../api/hoursTypes';
import type { adjustmentService } from '../../../../api/services/adjustmentService';
import type { customerPaymentService } from '../../../../api/services/financeService';
import type { policyService } from '../../../../api/services/policyService';
import { makePayment, page } from '../../../../test/financeFixtures';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { PaymentsTab } from '../payments/PaymentsTab';
import { usePurchaseAdjustments } from './usePurchaseAdjustments';
import { ActionButtons } from '../../../../components/lifecycle/ActionButtons';

const mocks = vi.hoisted(() => ({
  propose: vi.fn<typeof adjustmentService.propose>(),
  effective: vi.fn<typeof policyService.effective>(),
  listPayments: vi.fn<typeof customerPaymentService.list>(),
  getPayment: vi.fn<typeof customerPaymentService.get>(),
}));
vi.mock('../../../../api/services/adjustmentService', () => ({
  adjustmentService: { propose: mocks.propose },
}));
vi.mock('../../../../api/services/policyService', () => ({
  policyService: { effective: mocks.effective },
}));
vi.mock('../../../../api/services/financeService', () => ({
  customerPaymentService: { list: mocks.listPayments, get: mocks.getPayment },
  hireInvoiceService: { list: vi.fn() },
}));
vi.mock('../../../../api/services/customerService', () => ({
  customerService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }),
  },
}));
vi.mock('../../../../api/services/staffService', () => ({
  staffService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }),
  },
}));

const PURCHASE = {
  id: 'p1',
  purchase_number: 'HP-2026-00007',
  machine_id: 'm1',
  totals: { remaining: '10' },
} as HoursPurchaseDto;

const proposed = { id: 'r1' } as AdjustmentRequestDto;
const PROPOSE = [P.tenantAdjustmentPropose, P.tenantFinanceRead, P.tenantPolicyRead];

function Purchase({ live = true, refundAllowed = false }) {
  const { actions, dialogs } = usePurchaseAdjustments(PURCHASE, { live, refundAllowed });
  return (
    <>
      <ActionButtons actions={actions} />
      {dialogs}
    </>
  );
}

function renderPurchase(props: { live?: boolean; refundAllowed?: boolean }, perms = PROPOSE) {
  renderWithProviders(
    <Routes>
      <Route path="/" element={<Purchase {...props} />} />
      <Route path="/tenant/finance/adjustments/requests/:id" element={<p>Request page</p>} />
    </Routes>,
    { tenantPermissions: perms },
  );
}

const policy = (values: Record<string, unknown>) =>
  ({ values }) as Awaited<ReturnType<typeof policyService.effective>>;

beforeEach(() => {
  vi.clearAllMocks();
  mocks.effective.mockResolvedValue(policy({ adjustment_evidence_required: false }));
  mocks.propose.mockResolvedValue(proposed);
  mocks.listPayments.mockResolvedValue(page([makePayment({ status: 'VERIFIED' })]));
});

describe('hours purchase adjustments', () => {
  it('offers a refund only when the policy allows it', () => {
    renderPurchase({ refundAllowed: false });
    expect(screen.getByRole('button', { name: 'Correct hours' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reverse purchase' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Refund unused hours' })).not.toBeInTheDocument();
  });

  it('shows nothing without the propose permission', () => {
    renderPurchase({ refundAllowed: true }, [P.tenantFinanceRead]);
    expect(screen.queryByRole('button', { name: 'Correct hours' })).not.toBeInTheDocument();
  });

  it('sends a taken-off correction as negative hours and opens the request', async () => {
    const user = userEvent.setup();
    renderPurchase({});
    await user.click(screen.getByRole('button', { name: 'Correct hours' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Change/ }));
    await user.click(await screen.findByRole('option', { name: 'Take hours off' }));
    await user.type(within(dialog).getByRole('textbox', { name: /^Hours/ }), '2.5');
    await user.type(within(dialog).getByRole('textbox', { name: /^Reason/ }), 'Meter misread');
    await user.click(within(dialog).getByRole('button', { name: 'Propose correction' }));
    await waitFor(() => {
      expect(mocks.propose).toHaveBeenCalledWith(
        expect.objectContaining({
          request_type: 'HOURS_CORRECTION',
          purchase_id: 'p1',
          machine_id: 'm1',
          hours: '-2.5',
          consumed_entry_id: null,
        }),
        expect.any(String),
      );
    });
    expect(await screen.findByText('Request page')).toBeInTheDocument();
  });

  it('refuses to propose without evidence when the policy needs it', async () => {
    const user = userEvent.setup();
    mocks.effective.mockResolvedValue(policy({ adjustment_evidence_required: true }));
    renderPurchase({});
    await user.click(screen.getByRole('button', { name: 'Reverse purchase' }));
    const dialog = await screen.findByRole('dialog');
    await waitFor(() => {
      expect(mocks.effective).toHaveBeenCalled();
    });
    await user.type(within(dialog).getByRole('textbox', { name: /^Reason/ }), 'Wrong customer');
    await user.click(within(dialog).getByRole('button', { name: 'Propose reversal' }));
    expect(await within(dialog).findByText('Attach the supporting evidence')).toBeInTheDocument();
    expect(mocks.propose).not.toHaveBeenCalled();
  });

  it('needs the payout details when a refund is paid out', async () => {
    const user = userEvent.setup();
    renderPurchase({ refundAllowed: true });
    await user.click(screen.getByRole('button', { name: 'Refund unused hours' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /^Hours to refund/ }), '3');
    await user.type(within(dialog).getByRole('textbox', { name: /^Reason/ }), 'Job ended early');
    await user.click(within(dialog).getByRole('combobox', { name: /Settlement/ }));
    await user.click(await screen.findByRole('option', { name: 'Paid out to the customer' }));
    await user.click(within(dialog).getByRole('button', { name: 'Propose refund' }));
    expect(await within(dialog).findByText('Choose how it is paid out')).toBeInTheDocument();
    expect(mocks.propose).not.toHaveBeenCalled();
  });
});

describe('payment reversal', () => {
  const MENU = 'Actions for payment TRX-1';

  it('reverses a verified bank payment as a payment reversal', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <Routes>
        <Route path="/" element={<PaymentsTab timeZone="UTC" />} />
        <Route path="/tenant/finance/adjustments/requests/:id" element={<p>Request page</p>} />
      </Routes>,
      { tenantPermissions: PROPOSE },
    );
    await user.click(await screen.findByRole('button', { name: MENU }));
    await user.click(await screen.findByRole('menuitem', { name: 'Reverse' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /^Reason/ }), 'Bounced');
    await user.click(within(dialog).getByRole('button', { name: 'Propose reversal' }));
    await waitFor(() => {
      expect(mocks.propose).toHaveBeenCalledWith(
        expect.objectContaining({
          request_type: 'PAYMENT_REVERSAL',
          payment_id: '66666666-0000-4000-8000-000000000001',
        }),
        expect.any(String),
      );
    });
    expect(await screen.findByText('Request page')).toBeInTheDocument();
  });

  it('marks a reversed payment and offers no second reversal', async () => {
    const user = userEvent.setup();
    mocks.listPayments.mockResolvedValue(
      page([
        makePayment({
          status: 'VERIFIED',
          reversed_at: '2026-11-02T08:00:00Z',
          reversal_id: 'r1',
        }),
      ]),
    );
    renderWithProviders(<PaymentsTab timeZone="UTC" />, { tenantPermissions: PROPOSE });
    expect(await screen.findByText('Reversed')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: MENU }));
    expect(await screen.findByRole('menu')).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Reverse' })).not.toBeInTheDocument();
  });

  it('opens the payment named by a ledger link', async () => {
    mocks.getPayment.mockResolvedValue(makePayment({ reference: 'TRX-LINK' }));
    renderWithProviders(<PaymentsTab timeZone="UTC" />, {
      tenantPermissions: PROPOSE,
      route: '/tenant/finance?tab=payments&payment_id=pay1',
    });
    expect(await screen.findByText('Payment TRX-LINK')).toBeInTheDocument();
    expect(mocks.getPayment).toHaveBeenCalledWith('pay1', expect.any(AbortSignal));
    expect(mocks.listPayments.mock.lastCall?.[0].filters?.status).toBeUndefined();
  });
});
