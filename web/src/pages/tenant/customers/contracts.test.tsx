import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { customerService } from '../../../api/services/customerService';
import { STALE_RECORD_MESSAGE } from '../../../components/lifecycle/LifecycleActionDialog';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ContractsPanel } from './ContractsPanel';
import { CONTRACT_ID, CUSTOMER_ID, makeContract, makeCustomer } from './customerFixtures';

const mocks = vi.hoisted(() => ({
  listContracts: vi.fn<typeof customerService.listContracts>(),
  updateContract: vi.fn<typeof customerService.updateContract>(),
  closeContract: vi.fn<typeof customerService.closeContract>(),
  reopenContract: vi.fn<typeof customerService.reopenContract>(),
}));
vi.mock('../../../api/services/customerService', () => ({ customerService: mocks }));

const READ = ['tenant.customer.read'];
const WRITE = [...READ, 'tenant.customer.write'];
const MENU = 'Actions for contract K-7';
const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });
const apiError = (code: string, message: string) =>
  new ApiError({ status: code === 'STALE_VERSION' ? 409 : 422, code, message, correlationId: 'r' });

beforeEach(() => {
  mocks.listContracts.mockResolvedValue(page([makeContract()]));
});

function renderPanel(perms: string[]) {
  return renderWithProviders(<ContractsPanel customer={makeCustomer()} timeZone="UTC" />, {
    tenantPermissions: perms,
  });
}

async function openRowAction(user: ReturnType<typeof userEvent.setup>, item: string) {
  await user.click(await screen.findByRole('button', { name: MENU }));
  await user.click(screen.getByRole('menuitem', { name: item }));
}

describe('contracts of a customer', () => {
  it('filters by customer and passes the show-closed flag to the service', async () => {
    const user = userEvent.setup();
    renderPanel(READ);
    expect(await screen.findByText('K-7')).toBeInTheDocument();
    expect(mocks.listContracts.mock.calls[0]?.[0].filters).toEqual({
      customer_id: CUSTOMER_ID,
      include_inactive: undefined,
    });
    await user.click(screen.getByRole('switch', { name: 'Show closed' }));
    await waitFor(() => {
      expect(mocks.listContracts.mock.lastCall?.[0].filters).toMatchObject({
        include_inactive: 'true',
      });
    });
  });

  it('hides edit / close without tenant.customer.write', async () => {
    const user = userEvent.setup();
    renderPanel(READ);
    await user.click(await screen.findByRole('button', { name: MENU }));
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Close contract' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
  });

  it('closes with a required reason and the version read', async () => {
    const user = userEvent.setup();
    mocks.closeContract.mockResolvedValue(makeContract({ status: 'CLOSED', version: 3 }));
    renderPanel(WRITE);
    await openRowAction(user, 'Close contract');
    await user.click(screen.getByRole('button', { name: 'Close contract' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Work finished');
    await user.click(screen.getByRole('button', { name: 'Close contract' }));
    await waitFor(() => {
      expect(mocks.closeContract).toHaveBeenCalledTimes(1);
    });
    const [id, body] = mocks.closeContract.mock.calls[0] ?? [];
    expect(id).toBe(CONTRACT_ID);
    expect(body).toEqual({ reason: 'Work finished', version: 2 });
  });

  it('shows CONTRACT_HAS_OPEN_JOBS in the close dialog', async () => {
    const user = userEvent.setup();
    mocks.closeContract.mockRejectedValue(apiError('CONTRACT_HAS_OPEN_JOBS', 'Open jobs exist.'));
    renderPanel(WRITE);
    await openRowAction(user, 'Close contract');
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Work finished');
    await user.click(screen.getByRole('button', { name: 'Close contract' }));
    expect(await screen.findByText(/^CONTRACT_HAS_OPEN_JOBS: Open jobs exist\./)).toBeVisible();
  });

  it('reopens a closed contract and shows why it was closed', async () => {
    const user = userEvent.setup();
    const closed = makeContract({
      status: 'CLOSED',
      close_reason: 'Scope cut',
      closed_at: '2026-10-10T00:00:00Z',
    });
    mocks.listContracts.mockResolvedValue(page([closed]));
    mocks.reopenContract.mockResolvedValue(makeContract());
    renderPanel(WRITE);
    expect((await screen.findByText('K-7')).closest('tr')).toHaveAttribute('data-muted', 'true');
    await user.click(screen.getByText('K-7'));
    const drawer = await screen.findByRole('presentation');
    expect(within(drawer).getByText('Scope cut')).toBeInTheDocument();
    expect(within(drawer).queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
    await user.click(within(drawer).getByRole('button', { name: 'Reopen contract' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Extension signed');
    await user.click(screen.getByRole('button', { name: 'Reopen contract' }));
    await waitFor(() => {
      expect(mocks.reopenContract.mock.calls[0]?.[1]).toEqual({
        reason: 'Extension signed',
        version: 2,
      });
    });
  });
});

describe('edit contract', () => {
  async function toReview(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await screen.findByRole('textbox', { name: /Notes/ });
    await user.click(screen.getByRole('button', { name: 'Next' }));
  }

  it('is prefilled and submits with the version (customer not sent)', async () => {
    const user = userEvent.setup();
    mocks.updateContract.mockResolvedValue(makeContract({ reference: 'PO-2', version: 3 }));
    renderPanel(WRITE);
    await openRowAction(user, 'Edit');
    const ref = await screen.findByRole('textbox', { name: /Customer reference/ });
    expect(ref).toHaveValue('PO-1');
    await user.clear(ref);
    await user.type(ref, 'PO-2');
    await toReview(user);
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.updateContract).toHaveBeenCalledTimes(1);
    });
    const [id, body] = mocks.updateContract.mock.calls[0] ?? [];
    expect(id).toBe(CONTRACT_ID);
    expect(body).toEqual({
      contract_number: 'K-7',
      reference: 'PO-2',
      job_site_id: null,
      starts_on: '2026-10-01T00:00:00Z',
      ends_on: null,
      notes: null,
      version: 2,
    });
  });

  it('offers Reload on STALE_VERSION', async () => {
    const user = userEvent.setup();
    mocks.updateContract.mockRejectedValue(apiError('STALE_VERSION', 'Changed.'));
    renderPanel(WRITE);
    await openRowAction(user, 'Edit');
    await screen.findByRole('textbox', { name: /Customer reference/ });
    await toReview(user);
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText(STALE_RECORD_MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reload' }));
    await waitFor(() => {
      expect(mocks.listContracts).toHaveBeenCalledTimes(2);
    });
  });
});
