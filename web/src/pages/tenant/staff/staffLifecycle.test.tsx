import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { staffService } from '../../../api/services/staffService';
import type { StaffDto } from '../../../api/types';
import { STALE_RECORD_MESSAGE } from '../../../components/lifecycle/LifecycleActionDialog';
import { ACTIVE_RECORD } from '../../../test/lifecycleFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { StaffDetailPage } from './StaffDetailPage';
import { StaffPage } from './StaffPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof staffService.list>(),
  get: vi.fn<typeof staffService.get>(),
  update: vi.fn<typeof staffService.update>(),
  deactivate: vi.fn<typeof staffService.deactivate>(),
  reactivate: vi.fn<typeof staffService.reactivate>(),
}));
vi.mock('../../../api/services/staffService', () => ({ staffService: mocks }));

const READ = ['tenant.staff.read'];
const WRITE = ['tenant.staff.read', 'tenant.staff.write'];

function makeStaff(overrides: Partial<StaffDto> = {}): StaffDto {
  return {
    id: 's1',
    full_name: 'Asha Mwita',
    kind: 'OPERATOR',
    employee_code: 'E-1',
    phone: null,
    keycloak_subject: null,
    ...ACTIVE_RECORD,
    version: 4,
    ...overrides,
  };
}
const page = (items: StaffDto[]) => ({ items, total: items.length, page: 1, page_size: 25 });
const apiError = (code: string, message: string) =>
  new ApiError({ status: code === 'STALE_VERSION' ? 409 : 422, code, message, correlationId: 'c' });

beforeEach(() => {
  mocks.list.mockResolvedValue(page([makeStaff()]));
  mocks.get.mockResolvedValue(makeStaff());
});

async function menu(user: ReturnType<typeof userEvent.setup>, item: string) {
  await user.click(await screen.findByRole('button', { name: 'Actions for Asha Mwita' }));
  await user.click(screen.getByRole('menuitem', { name: item }));
}

describe('staff list', () => {
  it('passes include_inactive only when Show inactive is on', async () => {
    const user = userEvent.setup();
    renderWithProviders(<StaffPage />, { tenantPermissions: READ });
    expect(await screen.findByText('Asha Mwita')).toBeInTheDocument();
    expect(mocks.list.mock.calls[0]?.[0].filters?.include_inactive).toBeUndefined();
    await user.click(screen.getByRole('switch', { name: 'Show inactive' }));
    await waitFor(() => {
      expect(mocks.list.mock.lastCall?.[0].filters).toMatchObject({ include_inactive: 'true' });
    });
  });

  it('offers only View details without write permission or while read-only', async () => {
    const user = userEvent.setup();
    const { unmount } = renderWithProviders(<StaffPage />, { tenantPermissions: READ });
    await user.click(await screen.findByRole('button', { name: 'Actions for Asha Mwita' }));
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Deactivate' })).not.toBeInTheDocument();
    unmount();
    renderWithProviders(<StaffPage />, { tenantPermissions: WRITE, accessState: 'READ_ONLY' });
    await user.click(await screen.findByRole('button', { name: 'Actions for Asha Mwita' }));
    expect(screen.queryByRole('menuitem', { name: 'Deactivate' })).not.toBeInTheDocument();
  });

  it('deactivates with a required reason and the version, explaining consequences', async () => {
    const user = userEvent.setup();
    mocks.deactivate.mockResolvedValue(makeStaff({ is_active: false }));
    renderWithProviders(<StaffPage />, { tenantPermissions: WRITE });
    await menu(user, 'Deactivate');
    expect(screen.getByText(/open machine assignments are ended/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    expect(mocks.deactivate).not.toHaveBeenCalled();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Left the company');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    await waitFor(() => {
      expect(mocks.deactivate).toHaveBeenCalledTimes(1);
    });
    expect(mocks.deactivate.mock.calls[0]?.slice(0, 2)).toEqual([
      's1',
      { reason: 'Left the company', version: 4 },
    ]);
    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalledTimes(2);
    });
  });

  it('shows a business refusal with its hint', async () => {
    const user = userEvent.setup();
    mocks.deactivate.mockRejectedValue(apiError('STAFF_HOLDS_CASH', 'Holds cash.'));
    renderWithProviders(<StaffPage />, { tenantPermissions: WRITE });
    await menu(user, 'Deactivate');
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Left');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(
      await screen.findByText(/^STAFF_HOLDS_CASH: Holds cash\. — Record a cash handover/),
    ).toBeInTheDocument();
  });

  it('mutes inactive staff and reactivates them', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(page([makeStaff({ is_active: false })]));
    mocks.reactivate.mockResolvedValue(makeStaff());
    renderWithProviders(<StaffPage />, { tenantPermissions: WRITE });
    expect((await screen.findByText('Asha Mwita')).closest('tr')).toHaveAttribute(
      'data-muted',
      'true',
    );
    await menu(user, 'Reactivate');
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Rehired');
    await user.click(screen.getByRole('button', { name: 'Reactivate' }));
    await waitFor(() => {
      expect(mocks.reactivate.mock.calls[0]?.[1]).toEqual({ reason: 'Rehired', version: 4 });
    });
  });
});

describe('edit staff', () => {
  async function toReview(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await screen.findByRole('textbox', { name: /Login subject/ });
    await user.click(screen.getByRole('button', { name: 'Next' }));
  }

  it('is prefilled and submits with the version', async () => {
    const user = userEvent.setup();
    mocks.update.mockResolvedValue(makeStaff({ phone: '+255700', version: 5 }));
    renderWithProviders(<StaffPage />, { tenantPermissions: WRITE });
    await menu(user, 'Edit');
    expect(screen.getByRole('textbox', { name: /Full name/ })).toHaveValue('Asha Mwita');
    expect(screen.getByRole('textbox', { name: /Employee code/ })).toHaveValue('E-1');
    await user.type(screen.getByRole('textbox', { name: /Phone/ }), '+255700');
    await toReview(user);
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledTimes(1);
    });
    expect(mocks.update.mock.calls[0]?.[1]).toEqual({
      full_name: 'Asha Mwita',
      kind: 'OPERATOR',
      employee_code: 'E-1',
      phone: '+255700',
      keycloak_subject: null,
      version: 4,
    });
  });

  it('offers Reload on STALE_VERSION', async () => {
    const user = userEvent.setup();
    mocks.update.mockRejectedValue(apiError('STALE_VERSION', 'Stale'));
    renderWithProviders(<StaffDetailPage />, { tenantPermissions: WRITE });
    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    await toReview(user);
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText(STALE_RECORD_MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reload' }));
    await waitFor(() => {
      expect(mocks.get).toHaveBeenCalledTimes(2);
    });
  });
});

describe('staff details page', () => {
  it('shows all fields and the deactivation banner with its reason', async () => {
    mocks.get.mockResolvedValue(
      makeStaff({
        is_active: false,
        deactivation_reason: 'Left the company',
        deactivated_at: '2026-10-01T08:00:00Z',
      }),
    );
    renderWithProviders(<StaffDetailPage />, { tenantPermissions: WRITE });
    expect(await screen.findByRole('heading', { name: 'Asha Mwita' })).toBeInTheDocument();
    // The inactive banner is a status region; a still-loading section may be another one on slow runners.
    expect(screen.getByText(/Reason: Left the company/).closest('[role="status"]')).not.toBeNull();
    expect(screen.getByText('E-1')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reactivate' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
  });

  it('hides actions without write permission', async () => {
    renderWithProviders(<StaffDetailPage />, { tenantPermissions: READ });
    expect(await screen.findByRole('heading', { name: 'Asha Mwita' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument();
  });
});
