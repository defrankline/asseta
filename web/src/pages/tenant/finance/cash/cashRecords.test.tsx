import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../../access/permissionCodes';
import type {
  CashRetentionDto,
  CashTransferDto,
  RemittanceOverdueDto,
} from '../../../../api/custodyTypes';
import type { custodyService } from '../../../../api/services/custodyService';
import type { policyService } from '../../../../api/services/policyService';
import {
  recordPath,
  recordRoutePattern,
  type RecordKind,
} from '../../../../navigation/recordRoutes';
import { makeHandover, ME, OTHER_USER, page, STAFF_ID } from '../../../../test/financeFixtures';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import {
  CashRemittanceDetailPage,
  CashRetentionDetailPage,
  CashTransferDetailPage,
  RemittanceOverdueDetailPage,
} from './CashRecordPages';
import { RemittanceOverdueTab } from './RemittanceOverdueTab';

const RECEIVER_ID = '55555555-0000-4000-8000-000000000002';

const m = vi.hoisted(() => ({
  custodians: vi.fn<typeof custodyService.custodians>(),
  transfer: vi.fn<typeof custodyService.transfer>(),
  retention: vi.fn<typeof custodyService.retention>(),
  handover: vi.fn<typeof custodyService.handover>(),
  remittanceOverdue: vi.fn<typeof custodyService.remittanceOverdue>(),
  remittanceOverdueFlag: vi.fn<typeof custodyService.remittanceOverdueFlag>(),
  effective: vi.fn<typeof policyService.effective>(),
}));
vi.mock('../../../../api/services/custodyService', () => ({ custodyService: m }));
vi.mock('../../../../api/services/policyService', () => ({
  policyService: { effective: m.effective },
}));

function makeTransfer(o: Partial<CashTransferDto> = {}): CashTransferDto {
  return {
    id: 'tttttttt-0000-4000-8000-000000000001',
    client_id: null,
    from_staff_id: STAFF_ID,
    from_staff_name: 'Sam Supervisor',
    to_staff_id: RECEIVER_ID,
    to_staff_name: 'Omari Operator',
    amount_declared: '100000.0000',
    currency: 'TZS',
    transferred_at: '2026-10-21T08:00:00Z',
    note: null,
    status: 'ACKNOWLEDGED',
    source: 'WEB',
    recorded_by: OTHER_USER,
    recorded_by_name: 'Rita Recorder',
    recorded_at: '2026-10-21T08:05:00Z',
    amount_received: '100000.0000',
    ack_method: 'RECEIVER',
    acknowledged_by: '66666666-0000-4000-8000-000000000001',
    acknowledged_by_name: 'Omari Operator',
    acknowledged_at: '2026-10-21T09:00:00Z',
    ack_note: 'Counted',
    variance_id: null,
    ...o,
  };
}

function makeRetention(o: Partial<CashRetentionDto> = {}): CashRetentionDto {
  return {
    id: 'rrrrrrrr-0000-4000-8000-000000000001',
    client_id: null,
    staff_member_id: STAFF_ID,
    staff_member_name: 'Sam Supervisor',
    amount: '20000.0000',
    currency: 'TZS',
    reason_id: null,
    reason: 'Fuel float for the weekend',
    valid_until: null,
    status: 'PENDING',
    created_by: ME,
    created_by_name: 'Ops User',
    created_at: '2026-10-21T09:00:00Z',
    decided_by: null,
    decided_at: null,
    decision_note: null,
    ...o,
  };
}

function makeOverdue(o: Partial<RemittanceOverdueDto> = {}): RemittanceOverdueDto {
  return {
    id: 'oooooooo-0000-4000-8000-000000000009',
    staff_member_id: STAFF_ID,
    staff_member_name: 'Sam Supervisor',
    local_day: '2026-10-21',
    cutoff_hour: 18,
    amounts: [{ currency: 'TZS', amount: '75000.0000' }],
    flagged_at: '2026-10-21T15:05:00Z',
    policy_version: 'v3',
    ...o,
  };
}

/** Render a detail page on its exact-record route, as a notification link opens it. */
function openRecord(kind: RecordKind, id: string, page: ReactNode, permissions: string[]) {
  renderWithProviders(
    <Routes>
      <Route path={recordRoutePattern(kind)} element={page} />
    </Routes>,
    { tenantPermissions: permissions, route: recordPath(kind, id) },
  );
}

beforeEach(() => {
  m.custodians.mockResolvedValue(page([]));
  m.effective.mockResolvedValue({
    policy_type: 'CASH_CUSTODY',
    version_stamp: 'v1',
    values: { writeoff_requires_approval: true },
  } as unknown as Awaited<ReturnType<typeof policyService.effective>>);
});

describe('cash record detail pages (exact-record links)', () => {
  it('loads a transfer by its route id and shows names, status and history', async () => {
    m.transfer.mockResolvedValue(makeTransfer());
    openRecord('CASH_TRANSFER', makeTransfer().id, <CashTransferDetailPage />, [
      P.tenantFinanceRead,
      P.tenantDirectoryRead,
    ]);
    expect(
      await screen.findByRole('heading', {
        name: 'Cash transfer · Sam Supervisor → Omari Operator',
      }),
    ).toBeInTheDocument();
    expect(m.transfer).toHaveBeenCalledWith(makeTransfer().id, expect.any(AbortSignal));
    expect(screen.getByText('Acknowledged', { selector: '.MuiChip-label' })).toBeInTheDocument();
    const history = screen.getByRole('list', { name: 'History' });
    expect(within(history).getByText('Handed over by Sam Supervisor')).toBeInTheDocument();
    expect(within(history).getByText(/Rita Recorder/)).toBeInTheDocument();
    expect(within(history).getAllByText(/Omari Operator/).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: 'Cash transfers' })).toHaveAttribute(
      'href',
      '/tenant/finance/cash/transfers',
    );
  });

  it('falls back to a short id only when the server sent no name', async () => {
    m.transfer.mockResolvedValue(makeTransfer({ to_staff_name: null }));
    openRecord('CASH_TRANSFER', makeTransfer().id, <CashTransferDetailPage />, [
      P.tenantFinanceRead,
    ]);
    expect(
      await screen.findByRole('heading', { name: 'Cash transfer · Sam Supervisor → 55555555…' }),
    ).toBeInTheDocument();
  });

  it('offers the same decision as the list row, disabled on your own request', async () => {
    m.retention.mockResolvedValue(makeRetention());
    openRecord('CASH_RETENTION', makeRetention().id, <CashRetentionDetailPage />, [
      P.tenantFinanceRead,
      P.tenantFinanceRetentionApprove,
    ]);
    const decide = await screen.findByRole('button', { name: /Approve \/ reject/ });
    expect(decide).toBeDisabled();
    expect(
      screen.getByText(/unavailable\. Someone else must decide your own request/),
    ).toBeInTheDocument();
  });

  it("lets someone else decide another person's request", async () => {
    const user = userEvent.setup();
    m.retention.mockResolvedValue(makeRetention({ created_by: OTHER_USER }));
    openRecord('CASH_RETENTION', makeRetention().id, <CashRetentionDetailPage />, [
      P.tenantFinanceRead,
      P.tenantFinanceRetentionApprove,
    ]);
    await user.click(await screen.findByRole('button', { name: 'Approve / reject' }));
    expect(await screen.findByRole('dialog')).toHaveTextContent('Decide cash retention');
  });

  it('shows a remittance with the custodian and recorder names; confirming your own is disabled', async () => {
    m.handover.mockResolvedValue(
      makeHandover({
        staff_member_name: 'Sam Supervisor',
        recorded_by: ME,
        recorded_by_name: 'Ops User',
      }),
    );
    openRecord('CASH_REMITTANCE', makeHandover().id, <CashRemittanceDetailPage />, [
      P.tenantFinanceRead,
      P.tenantFinanceVerify,
    ]);
    expect(
      await screen.findByRole('heading', { name: 'Remittance · Sam Supervisor' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Confirm \/ reject/ })).toBeDisabled();
  });

  it('shows an overdue remittance flag with its cut-off and amounts', async () => {
    m.remittanceOverdueFlag.mockResolvedValue(makeOverdue());
    openRecord('REMITTANCE_OVERDUE', makeOverdue().id, <RemittanceOverdueDetailPage />, [
      P.tenantFinanceRead,
    ]);
    expect(
      await screen.findByRole('heading', {
        name: 'Remittance overdue · Sam Supervisor · 21 Oct 2026',
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText('18:00').length).toBeGreaterThan(0);
    expect(screen.getByText(/after the 18:00 cut-off/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open custody' })).toHaveAttribute(
      'href',
      expect.stringContaining(`staff_member_id=${STAFF_ID}`) as unknown,
    );
  });

  it('shows an error state when the record cannot be loaded', async () => {
    m.transfer.mockRejectedValue(new Error('boom'));
    openRecord('CASH_TRANSFER', 'missing', <CashTransferDetailPage />, [P.tenantFinanceRead]);
    expect(await screen.findByText('Could not load this cash transfer')).toBeInTheDocument();
  });
});

describe('RemittanceOverdueTab', () => {
  it('lists flags by custodian and filters by day range', async () => {
    const user = userEvent.setup();
    m.remittanceOverdue.mockResolvedValue(page([makeOverdue()]));
    renderWithProviders(<RemittanceOverdueTab timeZone="UTC" />, {
      tenantPermissions: [P.tenantFinanceRead],
    });
    expect(await screen.findByText('Sam Supervisor')).toBeInTheDocument();
    await user.type(screen.getByLabelText('From day'), '2026-10-01');
    await user.type(screen.getByLabelText('To day'), '2026-10-21');
    await waitFor(() => {
      expect(m.remittanceOverdue).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({
            day_from: '2026-10-01',
            day_to: '2026-10-21',
          }) as unknown,
        }),
        expect.any(AbortSignal),
      );
    });
  });
});
