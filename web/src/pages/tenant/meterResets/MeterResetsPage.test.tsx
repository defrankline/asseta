import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { meterService } from '../../../api/services/meterService';
import { MACHINE, ME_ID, makeReset } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { MeterResetsPage } from './MeterResetsPage';

const mocks = vi.hoisted(() => ({
  listResets: vi.fn<typeof meterService.listResets>(),
  decideReset: vi.fn<typeof meterService.decideReset>(),
}));
vi.mock('../../../api/services/meterService', () => ({
  meterService: { listResets: mocks.listResets, decideReset: mocks.decideReset },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: {
    list: vi.fn().mockResolvedValue({ items: [MACHINE], total: 1, page: 1, page_size: 200 }),
  },
}));

const APPROVER = ['tenant.meter.read', 'tenant.meter.approve', 'tenant.machine.read'];

beforeEach(() => {
  mocks.listResets.mockResolvedValue([
    makeReset(),
    makeReset({ id: '77777777-0000-4000-8000-000000000002', requested_by: ME_ID }),
  ]);
});

describe('MeterResetsPage', () => {
  it('lists pending resets company-wide by default with machine, reading and reason', async () => {
    renderWithProviders(<MeterResetsPage />, { tenantPermissions: APPROVER });
    const table = await screen.findByRole('table', { name: 'Meter resets' });
    expect(mocks.listResets).toHaveBeenCalledWith(
      { status: 'PENDING', machine_id: undefined },
      expect.any(AbortSignal),
    );
    expect(within(table).getAllByText('Hour meter replaced after failure')).toHaveLength(2);
    expect(within(table).getAllByText('9999.9 → 0.0')).toHaveLength(2);
    await waitFor(() => {
      expect(within(table).getAllByText(`${MACHINE.asset_code} · ${MACHINE.name}`)).toHaveLength(2);
    });
    // The requester's own reset cannot be decided by them.
    expect(within(table).getByText('You')).toBeInTheDocument();
    expect(
      within(table).getByRole('button', { name: /Decide reset \(You requested/ }),
    ).toBeDisabled();
  });

  it('decides a reset through the shared dialog and reloads', async () => {
    const user = userEvent.setup();
    mocks.decideReset.mockResolvedValue(makeReset({ status: 'APPROVED' }));
    renderWithProviders(<MeterResetsPage />, { tenantPermissions: APPROVER });
    const table = await screen.findByRole('table', { name: 'Meter resets' });
    await user.click(within(table).getByRole('button', { name: 'Decide' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: /^Approve reset/ }));
    await user.type(within(dialog).getByRole('textbox', { name: /Note/ }), 'Workshop card seen');
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(mocks.decideReset).toHaveBeenCalledWith(
        makeReset().id,
        { outcome: 'EXPLAINED', note: 'Workshop card seen' },
        expect.any(String),
      );
    });
    expect(await screen.findByText('Meter reset approved.')).toBeInTheDocument();
    await waitFor(() => {
      expect(mocks.listResets).toHaveBeenCalledTimes(2);
    });
  });

  it('can list every status', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MeterResetsPage />, { tenantPermissions: APPROVER });
    await screen.findByRole('table', { name: 'Meter resets' });
    await user.click(screen.getByRole('combobox', { name: 'Status' }));
    await user.click(await screen.findByRole('option', { name: 'All statuses' }));
    await waitFor(() => {
      expect(mocks.listResets).toHaveBeenLastCalledWith(
        { status: undefined, machine_id: undefined },
        expect.any(AbortSignal),
      );
    });
  });
});
