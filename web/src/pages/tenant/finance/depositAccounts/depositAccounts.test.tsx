import { screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../../access/permissionCodes';
import { ApiError } from '../../../../api/ApiError';
import type { DepositAccountDto } from '../../../../api/custodyTypes';
import type { depositAccountService } from '../../../../api/services/depositAccountService';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { DepositAccountDetailPage } from './DepositAccountDetailPage';
import { DepositAccountsPage } from './DepositAccountsPage';

const m = vi.hoisted(() => ({
  list: vi.fn<typeof depositAccountService.list>(),
  get: vi.fn<typeof depositAccountService.get>(),
  create: vi.fn<typeof depositAccountService.create>(),
  update: vi.fn<typeof depositAccountService.update>(),
  deactivate: vi.fn<typeof depositAccountService.deactivate>(),
  reactivate: vi.fn<typeof depositAccountService.reactivate>(),
}));
vi.mock('../../../../api/services/depositAccountService', () => ({
  depositAccountService: m,
  DEPOSIT_ACCOUNT_TYPES: ['BANK', 'MOBILE_MONEY', 'CASH_OFFICE'],
}));

const READ = [P.tenantFinanceRead];
const MANAGE = [P.tenantFinanceRead, P.tenantFinanceAccountsManage];

function makeAccount(o: Partial<DepositAccountDto> = {}): DepositAccountDto {
  return {
    id: 'acc-1',
    name: 'CRDB main',
    account_type: 'BANK',
    institution: 'CRDB',
    account_number_masked: '•••• 4821',
    currency: 'TZS',
    note: null,
    is_active: true,
    version: 3,
    created_at: '2026-10-20T08:00:00Z',
    created_by: null,
    created_by_name: 'Owner One',
    updated_at: '2026-10-20T08:00:00Z',
    deactivated_at: null,
    deactivated_by: null,
    deactivated_by_name: null,
    deactivation_reason: null,
    ...o,
  };
}
const page = (items: DepositAccountDto[]) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 25,
});

async function menu(user: UserEvent, item: string) {
  await user.click(await screen.findByRole('button', { name: 'Actions for CRDB main' }));
  await user.click(screen.getByRole('menuitem', { name: item }));
}

beforeEach(() => {
  m.list.mockResolvedValue(page([makeAccount()]));
  m.get.mockResolvedValue(makeAccount());
});

describe('deposit accounts list', () => {
  it('lists accounts with the masked number and filters by type and inactive', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DepositAccountsPage />, { tenantPermissions: READ });
    expect(await screen.findByText('CRDB main')).toBeInTheDocument();
    expect(screen.getByText('•••• 4821')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New deposit account' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: 'Type' }));
    await user.click(await screen.findByRole('option', { name: 'Mobile-money wallet' }));
    await user.click(screen.getByRole('switch', { name: 'Show inactive' }));
    await waitFor(() => {
      expect(m.list.mock.lastCall?.[0].filters).toMatchObject({
        account_type: 'MOBILE_MONEY',
        include_inactive: 'true',
      });
    });
  });

  it('creates an account through the stepper', async () => {
    const user = userEvent.setup();
    m.create.mockResolvedValue(makeAccount({ id: 'acc-2', name: 'M-Pesa till' }));
    renderWithProviders(<DepositAccountsPage />, { tenantPermissions: MANAGE });
    await user.click(await screen.findByRole('button', { name: 'New deposit account' }));
    await user.type(screen.getByRole('textbox', { name: /Name/ }), 'M-Pesa till');
    await user.click(screen.getByRole('combobox', { name: /Type/ }));
    await user.click(await screen.findByRole('option', { name: 'Mobile-money wallet' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.type(await screen.findByRole('textbox', { name: /Account number/ }), '0712 345 678');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Create account' }));
    await waitFor(() => {
      expect(m.create).toHaveBeenCalledTimes(1);
    });
    expect(m.create.mock.calls[0]?.[0]).toEqual({
      name: 'M-Pesa till',
      account_type: 'MOBILE_MONEY',
      institution: null,
      account_number: '0712 345 678',
      currency: null,
      note: null,
    });
  });

  it('edits with the version and keeps the stored number when none is typed', async () => {
    const user = userEvent.setup();
    m.update.mockResolvedValue(makeAccount({ version: 4 }));
    renderWithProviders(<DepositAccountsPage />, { tenantPermissions: MANAGE });
    await menu(user, 'Edit');
    expect(screen.getByRole('textbox', { name: /Name/ })).toHaveValue('CRDB main');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText(/Stored: •••• 4821/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(m.update).toHaveBeenCalledTimes(1);
    });
    expect(m.update.mock.calls[0]?.slice(0, 2)).toEqual([
      'acc-1',
      {
        name: 'CRDB main',
        account_type: 'BANK',
        institution: 'CRDB',
        account_number: null,
        currency: 'TZS',
        note: '',
        version: 3,
      },
    ]);
  });

  it('deactivates with a reason and the version, explaining the consequence', async () => {
    const user = userEvent.setup();
    m.deactivate.mockResolvedValue(makeAccount({ is_active: false }));
    renderWithProviders(<DepositAccountsPage />, { tenantPermissions: MANAGE });
    await menu(user, 'Deactivate');
    expect(screen.getByText(/New remittances can no longer name this account/)).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Account closed');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    await waitFor(() => {
      expect(m.deactivate.mock.calls[0]?.slice(0, 2)).toEqual([
        'acc-1',
        { reason: 'Account closed', version: 3 },
      ]);
    });
  });

  it('explains DUPLICATE_DEPOSIT_ACCOUNT', async () => {
    const user = userEvent.setup();
    m.create.mockRejectedValue(
      new ApiError({
        status: 409,
        code: 'DUPLICATE_DEPOSIT_ACCOUNT',
        message: 'A deposit account with this name already exists',
        correlationId: 'c',
      }),
    );
    renderWithProviders(<DepositAccountsPage />, { tenantPermissions: MANAGE });
    await user.click(await screen.findByRole('button', { name: 'New deposit account' }));
    await user.type(screen.getByRole('textbox', { name: /Name/ }), 'CRDB main');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Create account' }));
    expect(
      await screen.findByText(/Another deposit account already has this name/),
    ).toBeInTheDocument();
  });
});

describe('deposit account details', () => {
  it('shows the account and reactivates an inactive one', async () => {
    const user = userEvent.setup();
    m.get.mockResolvedValue(
      makeAccount({
        is_active: false,
        deactivation_reason: 'Account closed',
        deactivated_at: '2026-10-22T08:00:00Z',
      }),
    );
    m.reactivate.mockResolvedValue(makeAccount());
    renderWithProviders(<DepositAccountDetailPage />, { tenantPermissions: MANAGE });
    expect(await screen.findByRole('heading', { name: 'CRDB main' })).toBeInTheDocument();
    expect(screen.getByText(/Reason: Account closed/)).toBeInTheDocument();
    expect(screen.getByText('Bank account')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reactivate' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Reopened');
    await user.click(screen.getByRole('button', { name: 'Reactivate' }));
    await waitFor(() => {
      expect(m.reactivate.mock.calls[0]?.[1]).toEqual({ reason: 'Reopened', version: 3 });
    });
  });

  it('hides actions for finance readers', async () => {
    renderWithProviders(<DepositAccountDetailPage />, { tenantPermissions: READ });
    expect(await screen.findByRole('heading', { name: 'CRDB main' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument();
  });
});
