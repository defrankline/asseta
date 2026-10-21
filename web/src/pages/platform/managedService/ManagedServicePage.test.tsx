import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { mandateService } from '../../../api/services/mandateService';
import type { tenantService } from '../../../api/services/tenantService';
import type { MandateDto, TenantDto } from '../../../api/types';
import { TENANT_B } from '../../../test/fixtures';
import { MANDATE_ID, makeMandateDetail, STAFF_ID } from '../../../test/mandateFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ManagedServicePage } from './ManagedServicePage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof mandateService.list>(),
  get: vi.fn<typeof mandateService.get>(),
  grant: vi.fn<typeof mandateService.grant>(),
  listStaff: vi.fn<typeof mandateService.listStaff>(),
  listRoles: vi.fn<typeof mandateService.listRoles>(),
  assign: vi.fn<typeof mandateService.assign>(),
  removeAssignment: vi.fn<typeof mandateService.removeAssignment>(),
  end: vi.fn<typeof mandateService.end>(),
  listTenants: vi.fn<typeof tenantService.list>(),
  getTenant: vi.fn<typeof tenantService.get>(),
}));
vi.mock('../../../api/services/mandateService', () => ({ mandateService: mocks }));
vi.mock('../../../api/services/tenantService', () => ({
  tenantService: { list: mocks.listTenants, get: mocks.getTenant },
}));

const MANAGE = ['platform.mandate.read', 'platform.mandate.manage'];

const CLIENT: TenantDto = {
  id: TENANT_B,
  legal_name: 'Kilimo Haulage Ltd',
  display_name: 'Kilimo Haulage',
  registration_number: null,
  contact_name: 'Owner',
  contact_email: 'owner@kilimo.test',
  contact_phone: null,
  status: 'ACTIVE',
  access_state: 'FULL',
  access_state_reason: null,
  verification_status: 'VERIFIED',
  created_at: '2026-01-01T00:00:00Z',
};

function summary(): MandateDto {
  const detail: Partial<ReturnType<typeof makeMandateDetail>> = makeMandateDetail();
  delete detail.assignments;
  return detail as MandateDto;
}

beforeEach(() => {
  mocks.list.mockResolvedValue([summary()]);
  mocks.get.mockResolvedValue(makeMandateDetail());
  mocks.listTenants.mockResolvedValue({ items: [CLIENT], total: 1, page: 1, page_size: 20 });
  mocks.listStaff.mockResolvedValue([
    { user_id: STAFF_ID, email: 'amina@asseta.test', display_name: 'Amina Staff' },
  ]);
  mocks.listRoles.mockResolvedValue([{ key: 'dispatcher', permissions: ['tenant.job.write'] }]);
});

describe('ManagedServicePage', () => {
  it('searches clients on the server, submits the tenant id and refreshes the session', async () => {
    const user = userEvent.setup();
    const reload = vi.fn();
    mocks.grant.mockResolvedValue(makeMandateDetail({ tenant_id: TENANT_B }));
    renderWithProviders(<ManagedServicePage />, { permissions: MANAGE, session: { reload } });
    await user.click(await screen.findByRole('button', { name: 'Grant mandate' }));

    await user.type(screen.getByRole('combobox', { name: /Client tenant/ }), 'kili');
    // Debounced: one server query with the typed text, never a fetch-all filtered locally.
    await waitFor(() => {
      expect(mocks.listTenants).toHaveBeenLastCalledWith(
        { page: 1, page_size: 20, sort: 'name', q: 'kili' },
        expect.any(AbortSignal),
      );
    });
    expect(mocks.listTenants.mock.calls.some(([q]) => q.q === 'k' || q.q === 'kil')).toBe(false);
    await user.click(await screen.findByRole('option', { name: 'Kilimo Haulage' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.type(await screen.findByRole('textbox', { name: /Consent reference/ }), 'LTR-1');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Kilimo Haulage')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Grant mandate' }));

    await waitFor(() => {
      expect(mocks.grant).toHaveBeenCalledTimes(1);
    });
    expect(mocks.grant.mock.calls[0]?.[0]).toMatchObject({ tenant_id: TENANT_B, scope: 'FULL' });
    await waitFor(() => {
      expect(reload).toHaveBeenCalledTimes(1);
    });
  });

  it('assigns staff via server-searched staff and role pickers, then refreshes the session', async () => {
    const user = userEvent.setup();
    const reload = vi.fn();
    mocks.assign.mockResolvedValue(makeMandateDetail());
    renderWithProviders(<ManagedServicePage />, { permissions: MANAGE, session: { reload } });
    await user.click(await screen.findByText(summary().reference));
    const dialog = await screen.findByRole('dialog');

    await user.type(within(dialog).getByRole('combobox', { name: /Platform staff/ }), 'ami');
    await waitFor(() => {
      expect(mocks.listStaff).toHaveBeenLastCalledWith(expect.any(AbortSignal), 'ami');
    });
    await user.click(
      await screen.findByRole('option', { name: 'Amina Staff (amina@asseta.test)' }),
    );
    await user.type(within(dialog).getByRole('combobox', { name: /Client role/ }), 'disp');
    await waitFor(() => {
      expect(mocks.listRoles).toHaveBeenLastCalledWith(MANDATE_ID, expect.any(AbortSignal), 'disp');
    });
    await user.click(await screen.findByRole('option', { name: 'dispatcher' }));
    await user.click(within(dialog).getByRole('button', { name: 'Assign' }));

    await waitFor(() => {
      expect(mocks.assign).toHaveBeenCalledWith(
        MANDATE_ID,
        { user_id: STAFF_ID, role_key: 'dispatcher' },
        expect.any(String),
      );
    });
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
