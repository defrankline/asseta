import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { approvalService } from '../../../api/services/expenseService';
import { makeApproval, ME, page } from '../../../test/financeFixtures';
import { fakeSocketServer } from '../../../test/fakeWebSocket';
import { acceptSocket, LiveProviders, push } from '../../../test/realtimeHarness';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ApprovalsPage } from './ApprovalsPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof approvalService.list>(),
  decide: vi.fn<typeof approvalService.decide>(),
}));
vi.mock('../../../api/services/expenseService', () => ({
  approvalService: mocks,
  expenseService: { get: vi.fn() },
}));

const APPROVER = [P.tenantApprovalRead, P.tenantApprovalExpense];

beforeEach(() => {
  mocks.list.mockResolvedValue(
    page([makeApproval(), makeApproval({ id: 'own', reason: 'Own request', requested_by: ME })]),
  );
});

describe('ApprovalsPage', () => {
  it('lists pending requests with the policy reason and blocks self-approval', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ApprovalsPage />, { tenantPermissions: APPROVER });
    expect(await screen.findByText(/exceeds the auto-approval limit/)).toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledWith(
      expect.objectContaining({ filters: { status: 'PENDING' } }),
      expect.any(AbortSignal),
    );
    await user.click(screen.getByRole('button', { name: 'Actions for approval Own request' }));
    expect(screen.getByRole('menuitem', { name: /not allowed: your own request/ })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
  });

  it('rejects only with a reason', async () => {
    const user = userEvent.setup();
    mocks.decide.mockResolvedValue(makeApproval({ status: 'REJECTED' }));
    renderWithProviders(<ApprovalsPage />, { tenantPermissions: APPROVER });
    await user.click(
      await screen.findByRole('button', { name: /^Actions for approval Amount 250000/ }),
    );
    await user.click(screen.getByRole('menuitem', { name: 'Approve / reject' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Reject' }));
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    expect(await within(dialog).findByText('A reason is required to reject')).toBeInTheDocument();
    expect(mocks.decide).not.toHaveBeenCalled();
    await user.type(within(dialog).getByRole('textbox', { name: /Note/ }), 'No receipt');
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(mocks.decide).toHaveBeenCalledWith(
        makeApproval().id,
        { approve: false, note: 'No receipt' },
        expect.any(String),
      );
    });
  });

  it('shows no decision commands while READ_ONLY (view stays available)', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ApprovalsPage />, {
      tenantPermissions: [...APPROVER, P.tenantExpenseRead],
      accessState: 'READ_ONLY',
    });
    await user.click(
      await screen.findByRole('button', { name: /^Actions for approval Amount 250000/ }),
    );
    expect(screen.getByRole('menuitem', { name: 'View expense' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: /Approve/ })).not.toBeInTheDocument();
  });

  it('reloads itself when the server pushes an approval or expense change', async () => {
    const server = fakeSocketServer();
    renderWithProviders(
      <LiveProviders server={server}>
        <ApprovalsPage />
      </LiveProviders>,
      { tenantPermissions: APPROVER },
    );
    expect(await screen.findByText(/exceeds the auto-approval limit/)).toBeInTheDocument();
    const before = mocks.list.mock.calls.length;
    await acceptSocket(server);
    push(server, 'entity.changed', { entity: 'cash_handover', id: 'h1' });
    push(server, 'entity.changed', { entity: 'approval', id: 'a9', action: 'created' });
    await waitFor(() => {
      expect(mocks.list.mock.calls.length).toBe(before + 1);
    });
  });
});
