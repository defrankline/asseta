import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import { ApiError } from '../../../api/ApiError';
import type { tenantService } from '../../../api/services/tenantService';
import type { TenantDto } from '../../../api/types';
import { STALE_RECORD_MESSAGE } from '../../../components/lifecycle/LifecycleActionDialog';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { TenantDetailPage } from '../tenantDetail/TenantDetailPage';
import { TenantsPage } from './TenantsPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof tenantService.list>(),
  get: vi.fn<typeof tenantService.get>(),
  update: vi.fn<typeof tenantService.update>(),
}));
vi.mock('../../../api/services/tenantService', () => ({ tenantService: mocks }));

const TENANT_ID = '11111111-1111-4111-8111-111111111111';
function makeTenant(overrides: Partial<TenantDto> = {}): TenantDto {
  return {
    id: TENANT_ID,
    legal_name: 'Acme Plant Hire Ltd',
    display_name: 'Acme',
    registration_number: 'REG-1',
    contact_name: 'Jane Doe',
    contact_email: 'jane@acme.test',
    contact_phone: null,
    status: 'ACTIVE',
    access_state: 'FULL',
    access_state_reason: null,
    verification_status: 'UNVERIFIED',
    created_at: '2026-10-01T00:00:00Z',
    version: 4,
    ...overrides,
  };
}
const page = (items: TenantDto[]) => ({ items, total: items.length, page: 1, page_size: 25 });
const READ = [P.platformTenantRead];
const UPDATE = [P.platformTenantRead, P.platformTenantUpdate];

beforeEach(() => {
  mocks.list.mockResolvedValue(page([makeTenant()]));
  mocks.get.mockResolvedValue(makeTenant());
});

async function openEdit(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: 'Actions for Acme' }));
  await user.click(screen.getByRole('menuitem', { name: 'Edit company' }));
}

async function toReview(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByRole('textbox', { name: /Contact email/ });
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByRole('button', { name: 'Save changes' });
}

describe('tenant list row actions', () => {
  it('offers only View details without platform.tenant.update', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TenantsPage />, { permissions: READ });
    await user.click(await screen.findByRole('button', { name: 'Actions for Acme' }));
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Edit company' })).not.toBeInTheDocument();
  });

  it('mutes closed tenants and does not offer edits on them', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(page([makeTenant({ status: 'CLOSED' })]));
    renderWithProviders(<TenantsPage />, { permissions: UPDATE });
    expect((await screen.findByText('Acme')).closest('tr')).toHaveAttribute('data-muted', 'true');
    await user.click(screen.getByRole('button', { name: 'Actions for Acme' }));
    expect(screen.queryByRole('menuitem', { name: 'Edit company' })).not.toBeInTheDocument();
  });

  it('edits prefilled company details and saves with the version read', async () => {
    const user = userEvent.setup();
    mocks.update.mockResolvedValue(makeTenant({ display_name: 'Acme Hire', version: 5 }));
    renderWithProviders(<TenantsPage />, { permissions: UPDATE });
    await openEdit(user);
    const display = screen.getByRole('textbox', { name: /Display name/ });
    expect(display).toHaveValue('Acme');
    expect(screen.getByRole('textbox', { name: /Registration number/ })).toBeEnabled();
    await user.clear(display);
    await user.type(display, 'Acme Hire');
    await toReview(user);
    expect(screen.getByText('Acme Hire')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledTimes(1);
    });
    const [id, body] = mocks.update.mock.calls[0] ?? [];
    expect(id).toBe(TENANT_ID);
    expect(body).toEqual({
      legal_name: 'Acme Plant Hire Ltd',
      display_name: 'Acme Hire',
      registration_number: 'REG-1',
      contact_name: 'Jane Doe',
      contact_email: 'jane@acme.test',
      contact_phone: null,
      version: 4,
    });
    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalledTimes(2);
    });
  });

  it('locks the registration number once verified', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(page([makeTenant({ verification_status: 'VERIFIED' })]));
    renderWithProviders(<TenantsPage />, { permissions: UPDATE });
    await openEdit(user);
    expect(screen.getByRole('textbox', { name: /Registration number/ })).toBeDisabled();
    expect(screen.getByText('Fixed once the company is verified.')).toBeInTheDocument();
  });

  it('shows the server error and offers Reload on STALE_VERSION', async () => {
    const user = userEvent.setup();
    mocks.update.mockRejectedValue(
      new ApiError({ status: 409, code: 'STALE_VERSION', message: 'Stale', correlationId: 'c1' }),
    );
    renderWithProviders(<TenantsPage />, { permissions: UPDATE });
    await openEdit(user);
    await toReview(user);
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText(STALE_RECORD_MESSAGE)).toBeInTheDocument();
    expect(screen.getByText(/^STALE_VERSION: Stale/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reload' }));
    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalledTimes(2);
    });
  });

  it('shows business errors with a hint', async () => {
    const user = userEvent.setup();
    mocks.update.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'TENANT_EXISTS',
        message: 'Duplicate tenant.',
        correlationId: 'c2',
      }),
    );
    renderWithProviders(<TenantsPage />, { permissions: UPDATE });
    await openEdit(user);
    await toReview(user);
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(
      await screen.findByText(/^TENANT_EXISTS: Duplicate tenant\. — Another tenant/),
    ).toBeInTheDocument();
  });
});

describe('tenant details Edit button', () => {
  const renderDetail = (permissions: string[]) =>
    renderWithProviders(
      <Routes>
        <Route path="/platform/tenants/:tenantId" element={<TenantDetailPage />} />
      </Routes>,
      { permissions, route: `/platform/tenants/${TENANT_ID}` },
    );

  it('is hidden without platform.tenant.update', async () => {
    renderDetail(READ);
    expect(await screen.findByText('Acme Plant Hire Ltd', { selector: 'dd' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Edit company' })).not.toBeInTheDocument();
  });

  it('is shown with platform.tenant.update and hidden for closed tenants', async () => {
    const { unmount } = renderDetail(UPDATE);
    expect(await screen.findByRole('button', { name: 'Edit company' })).toBeInTheDocument();
    unmount();
    mocks.get.mockResolvedValue(makeTenant({ status: 'CLOSED' }));
    renderDetail(UPDATE);
    expect(await screen.findByText('Acme Plant Hire Ltd', { selector: 'dd' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Edit company' })).not.toBeInTheDocument();
  });
});
