import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { machineService } from '../../../api/services/machineService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { CreateMachineDialog } from './CreateMachineDialog';
import { EditMachineDialog, STALE_VERSION_MESSAGE } from './EditMachineDialog';
import { makeMachine } from './machineFixtures';

const mocks = vi.hoisted(() => ({
  listCategories: vi.fn<typeof machineService.listCategories>(),
  listAreas: vi.fn<typeof machineService.listAreas>(),
  create: vi.fn<typeof machineService.create>(),
  update: vi.fn<typeof machineService.update>(),
}));
vi.mock('../../../api/services/machineService', () => ({ machineService: mocks }));

const WRITE = ['tenant.machine.read', 'tenant.machine.write'];

beforeEach(() => {
  mocks.listCategories.mockResolvedValue([{ id: 'c1', name: 'Excavators', description: null }]);
  mocks.listAreas.mockResolvedValue([]);
});

/** Advance Identity → Classification → Metering → Review, waiting for each step to render. */
async function toReview(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByRole('combobox', { name: /Ownership/ });
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByRole('textbox', { name: /Capacity unit/ });
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByText('Meter decimal places');
}

describe('CreateMachineDialog', () => {
  it('walks to Review and submits nulls for empty optional fields', async () => {
    const user = userEvent.setup();
    mocks.create.mockResolvedValue(makeMachine());
    const onCreated = vi.fn();
    renderWithProviders(<CreateMachineDialog onClose={vi.fn()} onCreated={onCreated} />, {
      tenantPermissions: WRITE,
    });
    await user.type(screen.getByRole('textbox', { name: /Asset code/ }), 'EX-09');
    await user.type(screen.getByRole('textbox', { name: /^Name/ }), 'Dozer');
    await toReview(user);
    expect(await screen.findByText('EX-09')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create machine' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledTimes(1);
    });
    expect(mocks.create.mock.calls[0]?.[0]).toEqual({
      asset_code: 'EX-09',
      name: 'Dozer',
      manufacturer: null,
      model: null,
      serial_number: null,
      year_of_manufacture: null,
      category_id: null,
      operating_area_id: null,
      ownership: 'OWNED',
      meter_decimal_places: 1,
      capacity_value: null,
      capacity_unit: null,
    });
    expect(onCreated).toHaveBeenCalled();
  });

  it('searches categories on the server and submits the picked category id', async () => {
    const user = userEvent.setup();
    mocks.create.mockResolvedValue(makeMachine());
    renderWithProviders(<CreateMachineDialog onClose={vi.fn()} onCreated={vi.fn()} />, {
      tenantPermissions: WRITE,
    });
    await user.type(screen.getByRole('textbox', { name: /Asset code/ }), 'EX-09');
    await user.type(screen.getByRole('textbox', { name: /^Name/ }), 'Dozer');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.type(await screen.findByRole('combobox', { name: /Category/ }), 'Exc');
    await waitFor(() => {
      expect(mocks.listCategories).toHaveBeenLastCalledWith(expect.any(AbortSignal), 'Exc');
    });
    await user.click(await screen.findByRole('option', { name: 'Excavators' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await screen.findByRole('textbox', { name: /Capacity unit/ });
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Excavators')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create machine' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledTimes(1);
    });
    expect(mocks.create.mock.calls[0]?.[0]).toMatchObject({ category_id: 'c1' });
  });

  it('blocks Next while required identity fields are empty', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateMachineDialog onClose={vi.fn()} onCreated={vi.fn()} />, {
      tenantPermissions: WRITE,
    });
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Asset code is required')).toBeInTheDocument();
  });
});

describe('EditMachineDialog', () => {
  const machine = makeMachine({ version: 7 });

  it('sends the version that was read', async () => {
    const user = userEvent.setup();
    const saved = makeMachine({ version: 8 });
    mocks.update.mockResolvedValue(saved);
    const onSaved = vi.fn();
    renderWithProviders(
      <EditMachineDialog
        machine={machine}
        onClose={vi.fn()}
        onSaved={onSaved}
        onReloadRequested={vi.fn()}
      />,
      { tenantPermissions: WRITE },
    );
    await toReview(user);
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledTimes(1);
    });
    const [id, body] = mocks.update.mock.calls[0] ?? [];
    expect(id).toBe(machine.id);
    expect(body).toMatchObject({ version: 7, name: 'Excavator 1', status: 'ACTIVE' });
    expect(body).not.toHaveProperty('asset_code');
    expect(onSaved).toHaveBeenCalledWith(saved);
  });

  it('shows the existing category label and keeps its id', async () => {
    const user = userEvent.setup();
    mocks.update.mockResolvedValue(makeMachine({ version: 8 }));
    renderWithProviders(
      <EditMachineDialog
        machine={makeMachine({ version: 7, category_id: 'c1' })}
        onClose={vi.fn()}
        onSaved={vi.fn()}
        onReloadRequested={vi.fn()}
      />,
      { tenantPermissions: WRITE },
    );
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /Category/ })).toHaveValue('Excavators');
    });
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await screen.findByRole('textbox', { name: /Capacity unit/ });
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Excavators')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledTimes(1);
    });
    expect(mocks.update.mock.calls[0]?.[1]).toMatchObject({ category_id: 'c1' });
  });

  it('prompts a reload on STALE_VERSION', async () => {
    const user = userEvent.setup();
    mocks.update.mockRejectedValue(
      new ApiError({
        status: 409,
        code: 'STALE_VERSION',
        message: 'Machine was modified by someone else; reload and retry',
        correlationId: 'c',
      }),
    );
    const onReloadRequested = vi.fn();
    const onClose = vi.fn();
    renderWithProviders(
      <EditMachineDialog
        machine={machine}
        onClose={onClose}
        onSaved={vi.fn()}
        onReloadRequested={onReloadRequested}
      />,
      { tenantPermissions: WRITE },
    );
    await toReview(user);
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText(STALE_VERSION_MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reload' }));
    expect(onReloadRequested).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalled();
  });
});
