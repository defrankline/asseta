import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { machineService } from '../../../api/services/machineService';
import type { AreaDto, CategoryDto } from '../../../api/types';
import { STALE_RECORD_MESSAGE } from '../../../components/lifecycle/LifecycleActionDialog';
import { ACTIVE_RECORD } from '../../../test/lifecycleFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { MachinesPage } from './MachinesPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof machineService.list>(),
  listCategories: vi.fn<typeof machineService.listCategories>(),
  listAreas: vi.fn<typeof machineService.listAreas>(),
  createCategory: vi.fn<typeof machineService.createCategory>(),
  updateCategory: vi.fn<typeof machineService.updateCategory>(),
  deactivateCategory: vi.fn<typeof machineService.deactivateCategory>(),
  reactivateCategory: vi.fn<typeof machineService.reactivateCategory>(),
  updateArea: vi.fn<typeof machineService.updateArea>(),
  deactivateArea: vi.fn<typeof machineService.deactivateArea>(),
}));
vi.mock('../../../api/services/machineService', () => ({ machineService: mocks }));

const READ = ['tenant.machine.read'];
const WRITE = ['tenant.machine.read', 'tenant.machine.write'];
const CAT: CategoryDto = {
  id: 'c1',
  name: 'Excavators',
  description: 'Tracked diggers',
  ...ACTIVE_RECORD,
  version: 2,
};
const AREA: AreaDto = { id: 'a1', code: 'DSM', name: 'Dar es Salaam', ...ACTIVE_RECORD };

beforeEach(() => {
  mocks.list.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
  mocks.listCategories.mockResolvedValue([CAT]);
  mocks.listAreas.mockResolvedValue([AREA]);
});

async function openTab(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(screen.getByRole('tab', { name }));
}

describe('machine categories', () => {
  it('searches on the server and passes include_inactive when shown', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MachinesPage />, { tenantPermissions: READ });
    await openTab(user, 'Categories');
    expect(await screen.findByText('Tracked diggers')).toBeInTheDocument();
    expect(mocks.listCategories).toHaveBeenLastCalledWith(
      expect.any(AbortSignal),
      undefined,
      false,
    );
    await user.type(screen.getByRole('textbox', { name: 'Search categories' }), 'Exc');
    await waitFor(() => {
      expect(mocks.listCategories).toHaveBeenLastCalledWith(expect.any(AbortSignal), 'Exc', false);
    });
    await user.click(screen.getByRole('switch', { name: 'Show inactive' }));
    await waitFor(() => {
      expect(mocks.listCategories).toHaveBeenLastCalledWith(expect.any(AbortSignal), 'Exc', true);
    });
  });

  it('hides create and mutations without write permission', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MachinesPage />, { tenantPermissions: READ });
    await openTab(user, 'Categories');
    await user.click(await screen.findByRole('button', { name: 'Actions for Excavators' }));
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New category' })).not.toBeInTheDocument();
  });

  it('views a category in a drawer', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MachinesPage />, { tenantPermissions: WRITE });
    await openTab(user, 'Categories');
    await user.click(await screen.findByText('Excavators'));
    const drawer = await screen.findByRole('presentation');
    expect(within(drawer).getByRole('heading', { name: 'Excavators' })).toBeInTheDocument();
    expect(within(drawer).getByRole('button', { name: 'Deactivate' })).toBeInTheDocument();
  });

  it('edits prefilled with the version and offers Reload on STALE_VERSION', async () => {
    const user = userEvent.setup();
    mocks.updateCategory.mockRejectedValueOnce(
      new ApiError({ status: 409, code: 'STALE_VERSION', message: 'Stale', correlationId: 's' }),
    );
    renderWithProviders(<MachinesPage />, { tenantPermissions: WRITE });
    await openTab(user, 'Categories');
    await user.click(await screen.findByRole('button', { name: 'Actions for Excavators' }));
    await user.click(screen.getByRole('menuitem', { name: 'Edit' }));
    const name = screen.getByRole('textbox', { name: /Name/ });
    expect(name).toHaveValue('Excavators');
    await user.clear(name);
    await user.type(name, 'Crawler excavators');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.updateCategory.mock.calls[0]?.slice(0, 2)).toEqual([
        'c1',
        { name: 'Crawler excavators', description: 'Tracked diggers', version: 2 },
      ]);
    });
    expect(await screen.findByText(STALE_RECORD_MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reload' }));
    await waitFor(() => {
      expect(mocks.listCategories.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
  });

  it('deactivates with a required reason and reactivates an inactive one', async () => {
    const user = userEvent.setup();
    mocks.deactivateCategory.mockResolvedValue({ ...CAT, is_active: false });
    mocks.reactivateCategory.mockResolvedValue(CAT);
    renderWithProviders(<MachinesPage />, { tenantPermissions: WRITE });
    await openTab(user, 'Categories');
    await user.click(await screen.findByRole('button', { name: 'Actions for Excavators' }));
    await user.click(screen.getByRole('menuitem', { name: 'Deactivate' }));
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'No longer used');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    await waitFor(() => {
      expect(mocks.deactivateCategory.mock.calls[0]?.slice(0, 2)).toEqual([
        'c1',
        { reason: 'No longer used', version: 2 },
      ]);
    });
    mocks.listCategories.mockResolvedValue([{ ...CAT, is_active: false }]);
    await user.click(screen.getByRole('switch', { name: 'Show inactive' }));
    expect((await screen.findByText('Inactive')).closest('tr')).toHaveAttribute(
      'data-muted',
      'true',
    );
    await user.click(screen.getByRole('button', { name: 'Actions for Excavators' }));
    await user.click(screen.getByRole('menuitem', { name: 'Reactivate' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Back in the fleet');
    await user.click(screen.getByRole('button', { name: 'Reactivate' }));
    await waitFor(() => {
      expect(mocks.reactivateCategory).toHaveBeenCalledTimes(1);
    });
  });
});

describe('operating areas', () => {
  it('shows a business refusal on deactivate', async () => {
    const user = userEvent.setup();
    mocks.deactivateArea.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'AREA_INACTIVE',
        message: 'Inactive.',
        correlationId: 'x',
      }),
    );
    renderWithProviders(<MachinesPage />, { tenantPermissions: WRITE });
    await openTab(user, 'Operating areas');
    await user.click(
      await screen.findByRole('button', { name: 'Actions for DSM · Dar es Salaam' }),
    );
    await user.click(screen.getByRole('menuitem', { name: 'Deactivate' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Depot closed');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(await screen.findByText(/^AREA_INACTIVE: Inactive\./)).toBeInTheDocument();
  });

  it('edits an area with its version', async () => {
    const user = userEvent.setup();
    mocks.updateArea.mockResolvedValue({ ...AREA, name: 'Dar', version: 2 });
    renderWithProviders(<MachinesPage />, { tenantPermissions: WRITE });
    await openTab(user, 'Operating areas');
    await user.click(
      await screen.findByRole('button', { name: 'Actions for DSM · Dar es Salaam' }),
    );
    await user.click(screen.getByRole('menuitem', { name: 'Edit' }));
    expect(screen.getByRole('textbox', { name: /Code/ })).toHaveValue('DSM');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.updateArea.mock.calls[0]?.[1]).toEqual({
        code: 'DSM',
        name: 'Dar es Salaam',
        version: 1,
      });
    });
  });
});
