import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { trackerService } from '../../../api/services/trackerService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { RegisterTrackerDialog } from './RegisterTrackerDialog';
import { makeTracker } from './trackerFixtures';

const mocks = vi.hoisted(() => ({
  listModels: vi.fn<typeof trackerService.listModels>(),
  register: vi.fn<typeof trackerService.register>(),
}));
vi.mock('../../../api/services/trackerService', () => ({
  trackerService: { listModels: mocks.listModels, register: mocks.register },
}));

const MODEL_ID = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';

describe('RegisterTrackerDialog', () => {
  it('registers with an approved model and sends empty optional fields as null', async () => {
    const user = userEvent.setup();
    mocks.listModels.mockResolvedValue([
      {
        id: MODEL_ID,
        manufacturer: 'Teltonika',
        model: 'FMB920',
        adapter: 'TRACCAR',
        protocol: 'teltonika',
        declared_capabilities: ['GNSS', 'IGNITION'],
        approved: true,
        notes: null,
      },
    ]);
    const tracker = makeTracker();
    mocks.register.mockResolvedValue(tracker);
    const onRegistered = vi.fn();
    renderWithProviders(<RegisterTrackerDialog onClose={vi.fn()} onRegistered={onRegistered} />, {
      tenantPermissions: [P.tenantTrackerRead, P.tenantTrackerWrite],
    });
    await user.click(await screen.findByRole('combobox', { name: /Approved tracker model/ }));
    await user.click(await screen.findByRole('option', { name: 'Teltonika FMB920' }));
    expect(screen.getByText(/Declared capabilities/)).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /External device id/ }), '356938035643809');
    await user.type(screen.getByRole('textbox', { name: /^Label/ }), 'TRK-01');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Register tracker' }));
    await waitFor(() => {
      expect(mocks.register).toHaveBeenCalledTimes(1);
    });
    expect(mocks.register.mock.calls[0]?.[0]).toEqual({
      tracker_model_id: MODEL_ID,
      external_id: '356938035643809',
      label: 'TRK-01',
      sim_iccid: null,
      sim_msisdn: null,
      carrier: null,
      credentials_ref: null,
    });
    expect(onRegistered).toHaveBeenCalledWith(tracker);
  });
});
