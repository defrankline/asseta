import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../../access/permissionCodes';
import type { AdjustmentEntryDto, AdjustmentRequestDto } from '../../../../api/adjustmentTypes';
import type { adjustmentService } from '../../../../api/services/adjustmentService';
import { ME, OTHER_USER, page } from '../../../../test/financeFixtures';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { ADJUSTMENT_ROUTES, adjustmentRequestPath } from '../../../../navigation/adjustmentRoutes';
import { recordPath } from '../../../../navigation/recordRoutes';
import { notificationTargetPath } from '../../../../notifications/center/display';
import { AdjustmentRequestDetailPage } from './AdjustmentDetailPages';
import { AdjustmentRequestsPage } from './AdjustmentRequestsPage';
import { AdjustmentsLedgerPage } from './AdjustmentsLedgerPage';
import { adjustedRecordPath } from './adjustmentDisplay';

const mocks = vi.hoisted(() => ({
  listEntries: vi.fn<typeof adjustmentService.listEntries>(),
  getEntry: vi.fn<typeof adjustmentService.getEntry>(),
  exportCsv: vi.fn<typeof adjustmentService.exportCsv>(),
  listRequests: vi.fn<typeof adjustmentService.listRequests>(),
  getRequest: vi.fn<typeof adjustmentService.getRequest>(),
  propose: vi.fn<typeof adjustmentService.propose>(),
  decide: vi.fn<typeof adjustmentService.decide>(),
  withdraw: vi.fn<typeof adjustmentService.withdraw>(),
  saveBlob: vi.fn(),
}));
vi.mock('../../../../api/services/adjustmentService', () => ({ adjustmentService: mocks }));
vi.mock('../../../../components/data/exportFile', async (original) => ({
  ...(await original<typeof import('../../../../components/data/exportFile')>()),
  saveBlob: mocks.saveBlob,
}));

const ENTRY: AdjustmentEntryDto = {
  id: 'e1',
  adjustment_type: 'HOURS_REFUND',
  status: 'APPROVED',
  unit: 'HOURS',
  original_type: 'hours_purchase',
  original_id: 'p1',
  original_reference: 'HP-2026-00007',
  source_type: 'adjustment_request',
  source_id: 'r1',
  original_value: '10',
  new_value: '6',
  amount: '4',
  currency: 'TZS',
  resulting_balance: '6',
  reason_id: null,
  reason_label: 'Machine withdrawn',
  reason: 'Job ended early',
  evidence_attachment_ids: [],
  customer_id: 'c1',
  customer_name: 'Juma Construction',
  machine_id: null,
  staff_member_id: null,
  requested_by: OTHER_USER,
  requested_at: '2026-11-01T08:00:00Z',
  approved_by: ME,
  approved_at: '2026-11-01T09:00:00Z',
  decision_note: null,
  details: {},
  posted_at: '2026-11-01T09:00:00Z',
};

const request = (o: Partial<AdjustmentRequestDto> = {}): AdjustmentRequestDto => ({
  id: 'r1',
  client_id: null,
  request_type: 'PAYMENT_REVERSAL',
  status: 'PROPOSED',
  original_type: 'customer_payment',
  original_id: 'pay1',
  original_reference: 'TRX-1',
  purchase_id: null,
  customer_id: 'c1',
  customer_name: 'Juma Construction',
  machine_id: null,
  hours: null,
  amount: '500000',
  currency: 'TZS',
  settlement: null,
  reason: 'Bounced at the bank',
  reason_code_id: null,
  evidence_attachment_ids: [],
  params: {},
  effects: {
    unused_hours_removed: '8',
    used_hours: '2',
    money_owed: '100000',
    treatment: 'RECEIVABLE',
    purchases: [
      {
        purchase_id: 'p1',
        purchase_number: 'HP-2026-00007',
        unused_hours: '8',
        used_hours: '2',
        money_owed: '100000',
      },
    ],
  },
  proposed_by: OTHER_USER,
  proposed_at: '2026-11-01T08:00:00Z',
  decided_by: null,
  decided_at: null,
  decision_note: null,
  ...o,
});

const READ = [P.tenantAdjustmentRead];
const DECIDER = [...READ, P.tenantAdjustmentDecide, P.tenantAdjustmentPropose];

function renderRequest(permissions: string[]) {
  renderWithProviders(
    <Routes>
      <Route path={ADJUSTMENT_ROUTES.requestDetail} element={<AdjustmentRequestDetailPage />} />
    </Routes>,
    { tenantPermissions: permissions, route: adjustmentRequestPath('r1') },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.listEntries.mockResolvedValue(page([ENTRY]));
  mocks.listRequests.mockResolvedValue(page([request()]));
  mocks.getRequest.mockResolvedValue(request());
});

describe('AdjustmentsLedgerPage', () => {
  it('shows original, new and resulting values and filters by type chip', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdjustmentsLedgerPage />, { tenantPermissions: READ });
    const table = await screen.findByRole('table');
    expect(within(table).getByText('Hours refund')).toBeInTheDocument();
    expect(within(table).getByText('10 h')).toBeInTheDocument();
    expect(within(table).getAllByText('6 h')).toHaveLength(2);
    const types = screen.getByRole('group', { name: 'Adjustment type' });
    await user.click(within(types).getByText('Payment reversal'));
    await waitFor(() => {
      expect(mocks.listEntries.mock.lastCall?.[0].filters).toMatchObject({
        type: 'PAYMENT_REVERSAL',
      });
    });
  });

  it('exports the CSV with the chosen filters', async () => {
    const user = userEvent.setup();
    const file = { blob: new Blob(['a']), filename: 'adjustments.csv' };
    mocks.exportCsv.mockResolvedValue(file);
    renderWithProviders(<AdjustmentsLedgerPage />, {
      tenantPermissions: READ,
      route: `${ADJUSTMENT_ROUTES.ledger}?type=HOURS_REFUND`,
    });
    await screen.findByRole('table');
    await user.click(screen.getByRole('button', { name: 'Export CSV' }));
    await waitFor(() => {
      expect(mocks.saveBlob).toHaveBeenCalledWith(file.blob, 'adjustments.csv');
    });
    expect(mocks.exportCsv).toHaveBeenCalledWith({ type: 'HOURS_REFUND' });
  });
});

describe('AdjustmentRequestsPage', () => {
  it('opens on requests awaiting a decision', async () => {
    renderWithProviders(<AdjustmentRequestsPage />, { tenantPermissions: DECIDER });
    await screen.findByText('Bounced at the bank');
    expect(mocks.listRequests.mock.lastCall?.[0].filters).toMatchObject({ status: 'PROPOSED' });
    expect(screen.getByRole('button', { name: 'Decide' })).toBeEnabled();
  });

  it('disables deciding your own request', async () => {
    mocks.listRequests.mockResolvedValue(page([request({ proposed_by: ME })]));
    renderWithProviders(<AdjustmentRequestsPage />, { tenantPermissions: DECIDER });
    expect(
      await screen.findByRole('button', {
        name: 'Decide (Someone else must decide your own request)',
      }),
    ).toBeDisabled();
  });
});

describe('AdjustmentRequestDetailPage', () => {
  it('shows the forecast of hours deactivated and money owed while proposed', async () => {
    renderRequest(READ);
    expect(await screen.findByText('If approved (forecast)')).toBeInTheDocument();
    expect(screen.getAllByText('Hours deactivated').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Money owed').length).toBeGreaterThan(0);
    expect(screen.getByText('Billed to the customer')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'TRX-1' })).toHaveAttribute(
      'href',
      '/tenant/finance?tab=payments&payment_id=pay1',
    );
    expect(screen.queryByRole('button', { name: 'Decide' })).not.toBeInTheDocument();
  });

  it('says when the request can no longer be approved', async () => {
    mocks.getRequest.mockResolvedValue(
      request({ effects: { refused: 'PAYMENT_ALREADY_REVERSED' } }),
    );
    renderRequest(READ);
    expect(await screen.findByText(/This payment has already been reversed/)).toBeInTheDocument();
  });

  it('records a decision from someone else', async () => {
    const user = userEvent.setup();
    mocks.decide.mockResolvedValue(request({ status: 'APPROVED' }));
    renderRequest(DECIDER);
    await user.click(await screen.findByRole('button', { name: 'Decide' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Approve' }));
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(mocks.decide).toHaveBeenCalledWith(
        'r1',
        { decision: 'APPROVE', note: null },
        expect.any(String),
      );
    });
  });

  it('lets only the proposer withdraw, and never decide', async () => {
    const user = userEvent.setup();
    mocks.getRequest.mockResolvedValue(request({ proposed_by: ME }));
    mocks.withdraw.mockResolvedValue(request({ proposed_by: ME, status: 'WITHDRAWN' }));
    renderRequest(DECIDER);
    expect(await screen.findByRole('button', { name: 'Decide' })).toBeDisabled();
    expect(screen.getByText(/Someone else must decide your own request/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Withdraw' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'Raised in error');
    await user.click(within(dialog).getByRole('button', { name: 'Withdraw' }));
    await waitFor(() => {
      expect(mocks.withdraw).toHaveBeenCalledWith(
        'r1',
        { reason: 'Raised in error' },
        expect.any(String),
      );
    });
  });

  it('hides the withdraw of someone else’s request', async () => {
    renderRequest(DECIDER);
    await screen.findByRole('button', { name: 'Decide' });
    expect(screen.queryByRole('button', { name: 'Withdraw' })).not.toBeInTheDocument();
  });
});

describe('adjustment links', () => {
  it('opens the request from its notification', () => {
    expect(notificationTargetPath(null, { kind: 'ADJUSTMENT_REQUEST', record_id: 'r1' })).toBe(
      '/tenant/finance/adjustments/requests/r1',
    );
    expect(recordPath('ADJUSTMENT_ENTRY', 'e1')).toBe('/tenant/finance/adjustments/e1');
  });

  it('links an adjusted record to its page and leaves unknown types plain', () => {
    expect(adjustedRecordPath('hours_purchase', 'p1')).toBe('/tenant/hours/purchases/p1');
    expect(adjustedRecordPath('tenant_hire_invoice', 'i1')).toBe('/tenant/finance/invoices/i1');
    expect(adjustedRecordPath('job_activity', 'x')).toBeNull();
  });
});
