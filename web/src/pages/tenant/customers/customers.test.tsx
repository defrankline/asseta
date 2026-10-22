import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { customerService } from '../../../api/services/customerService';
import { STALE_RECORD_MESSAGE } from '../../../components/lifecycle/LifecycleActionDialog';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { CustomerDetailPage } from './CustomerDetailPage';
import { CUSTOMER_ID, makeContract, makeCustomer } from './customerFixtures';
import { CustomersPage } from './CustomersPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof customerService.list>(),
  get: vi.fn<typeof customerService.get>(),
  update: vi.fn<typeof customerService.update>(),
  deactivate: vi.fn<typeof customerService.deactivate>(),
  reactivate: vi.fn<typeof customerService.reactivate>(),
  listContracts: vi.fn<typeof customerService.listContracts>(),
  listRateCards: vi.fn<typeof customerService.listRateCards>(),
}));
vi.mock('../../../api/services/customerService', () => ({ customerService: mocks }));

const READ = ['tenant.customer.read'];
const WRITE = [...READ, 'tenant.customer.write'];
const MENU = 'Actions for C-01 · Acme Roads';
const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });
const conflict = (code: string, message: string) =>
  new ApiError({ status: code === 'STALE_VERSION' ? 409 : 422, code, message, correlationId: 'r' });

beforeEach(() => {
  mocks.list.mockResolvedValue(page([makeCustomer()]));
  mocks.get.mockResolvedValue(makeCustomer());
  mocks.listContracts.mockResolvedValue(page([makeContract()]));
  mocks.listRateCards.mockResolvedValue([]);
});

async function openRowAction(user: ReturnType<typeof userEvent.setup>, item: string) {
  await user.click(await screen.findByRole('button', { name: MENU }));
  await user.click(screen.getByRole('menuitem', { name: item }));
}

describe('customers list', () => {
  it('passes the show-inactive flag to the service and mutes inactive rows', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(
      page([makeCustomer(), makeCustomer({ id: 'x', code: 'C-02', is_active: false })]),
    );
    renderWithProviders(<CustomersPage />, { tenantPermissions: READ });
    expect((await screen.findByText('C-02')).closest('tr')).toHaveAttribute('data-muted', 'true');
    expect(mocks.list.mock.calls[0]?.[0].filters).toEqual({ include_inactive: undefined });
    await user.click(screen.getByRole('switch', { name: 'Show inactive' }));
    await waitFor(() => {
      expect(mocks.list.mock.lastCall?.[0].filters).toEqual({ include_inactive: 'true' });
    });
  });

  it('offers only View details without tenant.customer.write', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomersPage />, { tenantPermissions: READ });
    await user.click(await screen.findByRole('button', { name: MENU }));
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Deactivate' })).not.toBeInTheDocument();
  });

  it('hides mutations while the tenant is READ_ONLY', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomersPage />, { tenantPermissions: WRITE, accessState: 'READ_ONLY' });
    await user.click(await screen.findByRole('button', { name: MENU }));
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New customer' })).not.toBeInTheDocument();
  });

  it('deactivates only with a reason and sends reason + version', async () => {
    const user = userEvent.setup();
    mocks.deactivate.mockResolvedValue(makeCustomer({ is_active: false, version: 5 }));
    renderWithProviders(<CustomersPage />, { tenantPermissions: WRITE });
    await openRowAction(user, 'Deactivate');
    expect(screen.getByText(/balance and statement stay available/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    expect(mocks.deactivate).not.toHaveBeenCalled();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Went bankrupt');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    await waitFor(() => {
      expect(mocks.deactivate).toHaveBeenCalledTimes(1);
    });
    const [id, body] = mocks.deactivate.mock.calls[0] ?? [];
    expect(id).toBe(CUSTOMER_ID);
    expect(body).toEqual({ reason: 'Went bankrupt', version: 4 });
    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalledTimes(2);
    });
  });

  it('shows CUSTOMER_HAS_OPEN_JOBS in the dialog', async () => {
    const user = userEvent.setup();
    mocks.deactivate.mockRejectedValue(conflict('CUSTOMER_HAS_OPEN_JOBS', 'Has open jobs.'));
    renderWithProviders(<CustomersPage />, { tenantPermissions: WRITE });
    await openRowAction(user, 'Deactivate');
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Done here');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(
      await screen.findByText(/^CUSTOMER_HAS_OPEN_JOBS: Has open jobs\. — Complete or cancel/),
    ).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('reactivates an inactive customer', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(page([makeCustomer({ is_active: false })]));
    mocks.reactivate.mockResolvedValue(makeCustomer());
    renderWithProviders(<CustomersPage />, { tenantPermissions: WRITE });
    await openRowAction(user, 'Reactivate');
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Won back');
    await user.click(screen.getByRole('button', { name: 'Reactivate' }));
    await waitFor(() => {
      expect(mocks.reactivate.mock.calls[0]?.[1]).toEqual({ reason: 'Won back', version: 4 });
    });
  });
});

async function walkToReview(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByRole('textbox', { name: /Contact email/ });
  await user.click(screen.getByRole('button', { name: 'Next' }));
}

describe('edit customer', () => {
  it('is prefilled and submits with the version that was read', async () => {
    const user = userEvent.setup();
    mocks.update.mockResolvedValue(makeCustomer({ name: 'Acme Roads Ltd', version: 5 }));
    renderWithProviders(<CustomersPage />, { tenantPermissions: WRITE });
    await openRowAction(user, 'Edit');
    const name = await screen.findByRole('textbox', { name: /^Name/ });
    expect(name).toHaveValue('Acme Roads');
    expect(screen.getByRole('textbox', { name: /Payment terms/ })).toHaveValue('30');
    await user.clear(name);
    await user.type(name, 'Acme Roads Ltd');
    await walkToReview(user);
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledTimes(1);
    });
    const [id, body] = mocks.update.mock.calls[0] ?? [];
    expect(id).toBe(CUSTOMER_ID);
    expect(body).toEqual({
      code: 'C-01',
      name: 'Acme Roads Ltd',
      tax_id: null,
      payment_terms_days: 30,
      contact_name: 'Jane',
      contact_phone: '+255700000001',
      contact_email: null,
      version: 4,
    });
  });

  it('offers Reload on STALE_VERSION', async () => {
    const user = userEvent.setup();
    mocks.update.mockRejectedValue(conflict('STALE_VERSION', 'Changed by someone else.'));
    renderWithProviders(<CustomersPage />, { tenantPermissions: WRITE });
    await openRowAction(user, 'Edit');
    await screen.findByRole('textbox', { name: /^Name/ });
    await walkToReview(user);
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText(STALE_RECORD_MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reload' }));
    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalledTimes(2);
    });
  });
});

describe('customer details page', () => {
  it('shows fields, contracts and the inactive banner with its reason', async () => {
    mocks.get.mockResolvedValue(
      makeCustomer({
        is_active: false,
        deactivation_reason: 'Went bankrupt',
        deactivated_at: '2026-10-02T00:00:00Z',
      }),
    );
    renderWithProviders(<CustomerDetailPage />, { tenantPermissions: WRITE });
    expect(await screen.findByRole('heading', { name: 'C-01 · Acme Roads' })).toBeInTheDocument();
    // The inactive banner is a status region; a still-loading section may be another one on slow runners.
    const banner = screen.getByText(/Reason: Went bankrupt/).closest('[role="status"]');
    expect(banner).not.toBeNull();
    expect(await screen.findByText('K-7')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reactivate' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New contract' })).not.toBeInTheDocument();
  });

  it('hides record actions without write permission', async () => {
    renderWithProviders(<CustomerDetailPage />, { tenantPermissions: READ });
    expect(await screen.findByRole('heading', { name: 'C-01 · Acme Roads' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument();
  });

  it('shows Edit and Deactivate with write permission', async () => {
    renderWithProviders(<CustomerDetailPage />, { tenantPermissions: WRITE });
    expect(await screen.findByRole('button', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Deactivate' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New contract' })).toBeInTheDocument();
  });
});
