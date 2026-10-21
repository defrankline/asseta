import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { expenseCategoryService } from '../../../api/services/expenseCategoryService';
import type { expenseService, fuelService } from '../../../api/services/expenseService';
import type { ExpenseCategoryDto } from '../../../api/types';
import { makeExpense, page } from '../../../test/financeFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ExpensesPage } from './ExpensesPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof expenseService.list>(),
  submit: vi.fn<typeof expenseService.submit>(),
  receiptUrl: vi.fn<typeof expenseService.receiptUrl>(),
  fuelList: vi.fn<typeof fuelService.list>(),
  fuelRecord: vi.fn<typeof fuelService.record>(),
  categories: vi.fn<typeof expenseCategoryService.list>(),
}));
vi.mock('../../../api/services/expenseService', () => ({
  expenseService: {
    list: mocks.list,
    submit: mocks.submit,
    receiptUrl: mocks.receiptUrl,
    uploadReceipt: vi.fn(),
    get: vi.fn(),
  },
  fuelService: { list: mocks.fuelList, record: mocks.fuelRecord },
}));
vi.mock('../../../api/services/expenseCategoryService', () => ({
  expenseCategoryService: { list: mocks.categories, get: vi.fn() },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }),
  },
}));

const CATEGORY: ExpenseCategoryDto = {
  id: 'abababab-abab-4bab-8bab-abababababab',
  code: 'FUEL',
  name: 'Fuel',
  is_active: true,
  sync_revision: 1,
  deactivated_at: null,
  deactivation_reason: null,
  version: 1,
};
const READ = [P.tenantExpenseRead];
const WRITE = [P.tenantExpenseRead, P.tenantExpenseWrite];

beforeEach(() => {
  mocks.list.mockResolvedValue(page([makeExpense()]));
  mocks.categories.mockResolvedValue([CATEGORY]);
  mocks.fuelList.mockResolvedValue(page([]));
  mocks.receiptUrl.mockResolvedValue({ url: 'https://store.test/r.jpg', expires_in_seconds: 300 });
});

describe('ExpensesPage', () => {
  it('shows expense evidence: receipts via signed URL on demand, GPS, policy and approval state', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ExpensesPage />, { tenantPermissions: READ });
    expect(await screen.findByText('TZS 250,000.00')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Record expense' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Expense categories' })).toHaveAttribute(
      'href',
      '/tenant/expenses/categories',
    );
    await user.click(screen.getByText('Diesel for EX-01'));
    const drawer = await screen.findByRole('presentation');
    expect(within(drawer).getByText('EC:T3')).toBeInTheDocument();
    expect(
      within(drawer).getByText(/waiting for approval by someone other than the submitter/),
    ).toBeInTheDocument();
    expect(within(drawer).getByText(/-6.8, 39.28 ±12 m/)).toBeInTheDocument();
    expect(mocks.receiptUrl).not.toHaveBeenCalled();
    await user.click(within(drawer).getByRole('button', { name: 'View receipt 1' }));
    await waitFor(() => {
      expect(mocks.receiptUrl).toHaveBeenCalledWith(
        makeExpense().id,
        '99999999-0000-4000-8000-000000000001',
      );
    });
    expect(await within(drawer).findByAltText('Evidence thumbnail')).toHaveAttribute(
      'src',
      'https://store.test/r.jpg',
    );
  });

  it('records an expense from the console with category search and paid_from', async () => {
    const user = userEvent.setup();
    mocks.submit.mockResolvedValue(makeExpense({ status: 'APPROVED' }));
    renderWithProviders(<ExpensesPage />, { tenantPermissions: WRITE });
    await user.click(await screen.findByRole('button', { name: 'Record expense' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('combobox', { name: /Category/ }), 'fu');
    await waitFor(() => {
      expect(mocks.categories).toHaveBeenCalledWith(expect.any(AbortSignal), 'fu');
    });
    await user.click(await screen.findByRole('option', { name: 'FUEL · Fuel' }));
    await user.type(within(dialog).getByRole('textbox', { name: /Description/ }), 'Tyre repair');
    await user.type(within(dialog).getByRole('textbox', { name: /^Amount/ }), '45000');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('combobox', { name: /Paid from/ }));
    await user.click(await screen.findByRole('option', { name: 'Supervisor cash custody' }));
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Submit expense' }));
    await waitFor(() => {
      expect(mocks.submit).toHaveBeenCalledTimes(1);
    });
    expect(mocks.submit.mock.calls[0]?.[0]).toMatchObject({
      category_id: CATEGORY.id,
      description: 'Tyre repair',
      amount: '45000',
      paid_from: 'CASH_CUSTODY',
      custodian_staff_id: null,
      receipt_attachment_ids: [],
      gps: null,
      job_id: null,
      machine_id: null,
    });
  });

  it('records a fuel issue event', async () => {
    const user = userEvent.setup();
    mocks.fuelRecord.mockResolvedValue({
      id: 'f1',
      client_id: null,
      event_type: 'ISSUE',
      litres: '40',
      unit_price: '3200',
      attributed_cost: '128000.0000',
      currency: 'TZS',
      machine_id: null,
      job_id: null,
      expense_id: null,
      meter_reading: null,
      supplier: null,
      occurred_at: '2026-10-21T07:00:00Z',
      note: null,
      source: 'API',
      recorded_by: null,
    });
    renderWithProviders(<ExpensesPage />, { tenantPermissions: WRITE, route: '/?tab=fuel' });
    await user.click(await screen.findByRole('button', { name: 'Record fuel' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /^Litres/ }), '40');
    await user.type(within(dialog).getByRole('textbox', { name: /Unit price/ }), '3200');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Record fuel event' }));
    await waitFor(() => {
      expect(mocks.fuelRecord.mock.calls[0]?.[0]).toMatchObject({
        event_type: 'ISSUE',
        litres: '40',
        unit_price: '3200',
        expense_id: null,
      });
    });
  });
});
