import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import { ApiError } from '../../../api/ApiError';
import type { expenseCategoryService } from '../../../api/services/expenseCategoryService';
import type { ExpenseCategoryDto } from '../../../api/types';
import { STALE_RECORD_MESSAGE } from '../../../components/lifecycle/LifecycleActionDialog';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ExpenseCategoriesPage } from './ExpenseCategoriesPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof expenseCategoryService.list>(),
  create: vi.fn<typeof expenseCategoryService.create>(),
  update: vi.fn<typeof expenseCategoryService.update>(),
  deactivate: vi.fn<typeof expenseCategoryService.deactivate>(),
  reactivate: vi.fn<typeof expenseCategoryService.reactivate>(),
}));
vi.mock('../../../api/services/expenseCategoryService', () => ({
  expenseCategoryService: mocks,
}));

const CATEGORY: ExpenseCategoryDto = {
  id: 'abababab-abab-4bab-8bab-abababababab',
  code: 'FUEL',
  name: 'Fuel',
  is_active: true,
  sync_revision: 1,
  deactivated_at: null,
  deactivation_reason: null,
  version: 2,
};
const READ = [P.tenantExpenseRead];
const MANAGE = [P.tenantExpenseRead, P.tenantExpenseCategoryManage];
const MENU = 'Actions for FUEL · Fuel';

beforeEach(() => {
  mocks.list.mockResolvedValue([CATEGORY]);
});

describe('ExpenseCategoriesPage', () => {
  it('hides writes without the manage permission or while READ_ONLY', async () => {
    const user = userEvent.setup();
    const { unmount } = renderWithProviders(<ExpenseCategoriesPage />, { tenantPermissions: READ });
    await user.click(await screen.findByRole('button', { name: MENU }));
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Deactivate' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New category' })).not.toBeInTheDocument();
    unmount();
    renderWithProviders(<ExpenseCategoriesPage />, {
      tenantPermissions: MANAGE,
      accessState: 'READ_ONLY',
    });
    expect(await screen.findByText('FUEL')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New category' })).not.toBeInTheDocument();
  });

  it('passes the search text and show-inactive flag to the service', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ExpenseCategoriesPage />, { tenantPermissions: READ });
    expect(await screen.findByText('FUEL')).toBeInTheDocument();
    expect(mocks.list).toHaveBeenLastCalledWith(expect.any(AbortSignal), '', false);
    await user.click(screen.getByRole('switch', { name: 'Show inactive' }));
    await waitFor(() => {
      expect(mocks.list).toHaveBeenLastCalledWith(expect.any(AbortSignal), '', true);
    });
    await user.type(screen.getByRole('textbox', { name: 'Search code or name' }), 'fu');
    await waitFor(() => {
      expect(mocks.list).toHaveBeenLastCalledWith(expect.any(AbortSignal), 'fu', true);
    });
  });

  it('creates a category', async () => {
    const user = userEvent.setup();
    mocks.create.mockResolvedValue({ ...CATEGORY, id: 'n', code: 'TOLL', name: 'Tolls' });
    renderWithProviders(<ExpenseCategoriesPage />, { tenantPermissions: MANAGE });
    await user.click(await screen.findByRole('button', { name: 'New category' }));
    await user.type(screen.getByRole('textbox', { name: /Code/ }), 'TOLL');
    await user.type(screen.getByRole('textbox', { name: /Name/ }), 'Tolls');
    await user.click(screen.getByRole('button', { name: 'Create category' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith(
        { code: 'TOLL', name: 'Tolls' },
        expect.any(String),
      );
    });
  });

  it('edits a prefilled category with its version and offers Reload on STALE_VERSION', async () => {
    const user = userEvent.setup();
    mocks.update.mockRejectedValue(
      new ApiError({ status: 409, code: 'STALE_VERSION', message: 'Stale', correlationId: 'e1' }),
    );
    renderWithProviders(<ExpenseCategoriesPage />, { tenantPermissions: MANAGE });
    await user.click(await screen.findByRole('button', { name: MENU }));
    await user.click(screen.getByRole('menuitem', { name: 'Edit' }));
    const name = screen.getByRole('textbox', { name: /Name/ });
    expect(name).toHaveValue('Fuel');
    expect(screen.getByRole('textbox', { name: /Code/ })).toHaveValue('FUEL');
    await user.clear(name);
    await user.type(name, 'Fuel & oil');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledWith(
        CATEGORY.id,
        { code: 'FUEL', name: 'Fuel & oil', version: 2 },
        expect.any(String),
      );
    });
    expect(await screen.findByText(STALE_RECORD_MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reload' }));
    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalledTimes(2);
    });
  });

  it('deactivates only with a reason and shows a server refusal', async () => {
    const user = userEvent.setup();
    mocks.deactivate
      .mockRejectedValueOnce(
        new ApiError({
          status: 422,
          code: 'CATEGORY_IN_USE',
          message: 'Category has pending expenses.',
          correlationId: 'e2',
        }),
      )
      .mockResolvedValue({ ...CATEGORY, is_active: false });
    renderWithProviders(<ExpenseCategoriesPage />, { tenantPermissions: MANAGE });
    await user.click(await screen.findByRole('button', { name: MENU }));
    await user.click(screen.getByRole('menuitem', { name: 'Deactivate' }));
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    expect(mocks.deactivate).not.toHaveBeenCalled();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Merged into Fuel');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(
      await screen.findByText(/^CATEGORY_IN_USE: Category has pending expenses\./),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    await waitFor(() => {
      expect(mocks.deactivate).toHaveBeenCalledTimes(2);
    });
    expect(mocks.deactivate.mock.calls[1]?.[1]).toEqual({
      reason: 'Merged into Fuel',
      version: 2,
    });
  });

  it('reactivates an inactive category from its details drawer', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue([
      {
        ...CATEGORY,
        is_active: false,
        deactivation_reason: 'Merged',
        deactivated_at: '2026-10-01T00:00:00Z',
      },
    ]);
    mocks.reactivate.mockResolvedValue(CATEGORY);
    renderWithProviders(<ExpenseCategoriesPage />, { tenantPermissions: MANAGE });
    const row = (await screen.findByText('FUEL')).closest('tr');
    expect(row).toHaveAttribute('data-muted', 'true');
    await user.click(screen.getByText('FUEL'));
    expect(await screen.findByText('Merged')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reactivate' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Needed again');
    await user.click(screen.getByRole('button', { name: 'Reactivate' }));
    await waitFor(() => {
      expect(mocks.reactivate.mock.calls[0]?.[1]).toEqual({ reason: 'Needed again', version: 2 });
    });
  });
});
