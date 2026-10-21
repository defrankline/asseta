import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import { ApiError } from '../../../api/ApiError';
import type {
  gatewayService,
  trackerModelService,
} from '../../../api/services/platformCatalogService';
import type { GatewayDto, TrackerModelDto } from '../../../api/types';
import { STALE_RECORD_MESSAGE } from '../../../components/lifecycle/LifecycleActionDialog';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { GATEWAY_KEY_WARNING } from './GatewayDialogs';
import { TelemetryCatalogPage } from './TelemetryCatalogPage';

const models = vi.hoisted(() => ({
  list: vi.fn<typeof trackerModelService.list>(),
  create: vi.fn<typeof trackerModelService.create>(),
  update: vi.fn<typeof trackerModelService.update>(),
  deactivate: vi.fn<typeof trackerModelService.deactivate>(),
  reactivate: vi.fn<typeof trackerModelService.reactivate>(),
}));
const gateways = vi.hoisted(() => ({
  list: vi.fn<typeof gatewayService.list>(),
  create: vi.fn<typeof gatewayService.create>(),
  deactivate: vi.fn<typeof gatewayService.deactivate>(),
  reactivate: vi.fn<typeof gatewayService.reactivate>(),
}));
vi.mock('../../../api/services/platformCatalogService', () => ({
  trackerModelService: models,
  gatewayService: gateways,
}));

const MODEL: TrackerModelDto = {
  id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
  manufacturer: 'Teltonika',
  model: 'FMB920',
  adapter: 'TRACCAR',
  protocol: 'teltonika',
  declared_capabilities: ['GNSS', 'IGNITION'],
  approved: true,
  notes: null,
  deactivated_at: null,
  deactivation_reason: null,
  version: 3,
};
const GATEWAY: GatewayDto = {
  id: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
  name: 'Traccar EU',
  adapter: 'TRACCAR',
  active: true,
  last_seen_at: null,
  created_at: '2026-10-01T00:00:00Z',
};
const MODELS_READ = [P.platformTrackerModelRead];
const MODELS_MANAGE = [P.platformTrackerModelRead, P.platformTrackerModelManage];
const GW_MANAGE = [P.platformTrackerModelRead, P.platformGatewayRead, P.platformGatewayManage];
const MENU = 'Actions for Teltonika FMB920';

beforeEach(() => {
  models.list.mockResolvedValue([MODEL]);
  gateways.list.mockResolvedValue([GATEWAY]);
});

describe('tracker models tab', () => {
  it('hides Add and lifecycle actions without manage, and the Gateways tab without read', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TelemetryCatalogPage />, { permissions: MODELS_READ });
    await user.click(await screen.findByRole('button', { name: MENU }));
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Withdraw' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add tracker model' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Gateways' })).not.toBeInTheDocument();
  });

  it('passes the search text and the show-withdrawn flag to the service', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TelemetryCatalogPage />, { permissions: MODELS_READ });
    expect(await screen.findByText('FMB920')).toBeInTheDocument();
    expect(models.list).toHaveBeenLastCalledWith(expect.any(AbortSignal), '', false);
    await user.click(screen.getByRole('switch', { name: 'Show withdrawn' }));
    await waitFor(() => {
      expect(models.list).toHaveBeenLastCalledWith(expect.any(AbortSignal), '', true);
    });
    await user.type(screen.getByRole('textbox', { name: 'Search tracker models' }), 'osm');
    await waitFor(() => {
      expect(models.list).toHaveBeenLastCalledWith(expect.any(AbortSignal), 'osm', true);
    });
  });

  it('withdraws only with a reason and sends the version', async () => {
    const user = userEvent.setup();
    models.deactivate.mockResolvedValue({ ...MODEL, approved: false });
    renderWithProviders(<TelemetryCatalogPage />, { permissions: MODELS_MANAGE });
    await user.click(await screen.findByRole('button', { name: MENU }));
    await user.click(screen.getByRole('menuitem', { name: 'Withdraw' }));
    expect(screen.getByText(/can no longer register new trackers/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Withdraw' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    expect(models.deactivate).not.toHaveBeenCalled();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Vendor end of life');
    await user.click(screen.getByRole('button', { name: 'Withdraw' }));
    await waitFor(() => {
      expect(models.deactivate).toHaveBeenCalledTimes(1);
    });
    const [id, body] = models.deactivate.mock.calls[0] ?? [];
    expect(id).toBe(MODEL.id);
    expect(body).toEqual({ reason: 'Vendor end of life', version: 3 });
  });

  it('shows the server error in the withdraw dialog', async () => {
    const user = userEvent.setup();
    models.deactivate.mockRejectedValue(
      new ApiError({
        status: 409,
        code: 'ALREADY_INACTIVE',
        message: 'Already withdrawn.',
        correlationId: 'm1',
      }),
    );
    renderWithProviders(<TelemetryCatalogPage />, { permissions: MODELS_MANAGE });
    await user.click(await screen.findByRole('button', { name: MENU }));
    await user.click(screen.getByRole('menuitem', { name: 'Withdraw' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Old');
    await user.click(screen.getByRole('button', { name: 'Withdraw' }));
    expect(await screen.findByText(/^ALREADY_INACTIVE: Already withdrawn\./)).toBeInTheDocument();
  });

  it('restores a withdrawn model', async () => {
    const user = userEvent.setup();
    models.list.mockResolvedValue([{ ...MODEL, approved: false }]);
    models.reactivate.mockResolvedValue(MODEL);
    renderWithProviders(<TelemetryCatalogPage />, { permissions: MODELS_MANAGE });
    expect((await screen.findByText('FMB920')).closest('tr')).toHaveAttribute('data-muted', 'true');
    await user.click(screen.getByRole('button', { name: MENU }));
    await user.click(screen.getByRole('menuitem', { name: 'Restore' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Firmware fixed');
    await user.click(screen.getByRole('button', { name: 'Restore' }));
    await waitFor(() => {
      expect(models.reactivate.mock.calls[0]?.[1]).toEqual({
        reason: 'Firmware fixed',
        version: 3,
      });
    });
  });

  it('edits a prefilled model with the version and offers Reload on STALE_VERSION', async () => {
    const user = userEvent.setup();
    models.update.mockRejectedValueOnce(
      new ApiError({ status: 409, code: 'STALE_VERSION', message: 'Stale', correlationId: 'm2' }),
    );
    renderWithProviders(<TelemetryCatalogPage />, { permissions: MODELS_MANAGE });
    await user.click(await screen.findByRole('button', { name: MENU }));
    await user.click(screen.getByRole('menuitem', { name: 'Edit' }));
    const modelField = screen.getByRole('textbox', { name: /^Model/ });
    expect(modelField).toHaveValue('FMB920');
    expect(screen.getByRole('combobox', { name: /Adapter/ })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
    await user.clear(modelField);
    await user.type(modelField, 'FMB920 v2');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await screen.findByRole('checkbox', { name: 'Ignition' });
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(models.update).toHaveBeenCalledTimes(1);
    });
    expect(models.update.mock.calls[0]?.[1]).toEqual({
      manufacturer: 'Teltonika',
      model: 'FMB920 v2',
      protocol: 'teltonika',
      declared_capabilities: ['GNSS', 'IGNITION'],
      notes: null,
      version: 3,
    });
    expect(await screen.findByText(STALE_RECORD_MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reload' }));
    await waitFor(() => {
      expect(models.list).toHaveBeenCalledTimes(2);
    });
  });
});

describe('gateways tab', () => {
  async function openGateways(user: ReturnType<typeof userEvent.setup>, perms = GW_MANAGE) {
    renderWithProviders(<TelemetryCatalogPage />, { permissions: perms });
    await user.click(await screen.findByRole('tab', { name: 'Gateways' }));
    expect(await screen.findByText('Traccar EU')).toBeInTheDocument();
  }

  it('shows the new key once after create, with the warning', async () => {
    const user = userEvent.setup();
    gateways.create.mockResolvedValue({
      id: 'g2',
      name: 'Traccar AF',
      adapter: 'TRACCAR',
      gateway_key: 'gk_secret_123',
    });
    await openGateways(user);
    await user.click(screen.getByRole('button', { name: 'Add gateway' }));
    await user.type(screen.getByRole('textbox', { name: /Name/ }), 'Traccar AF');
    await user.click(screen.getByRole('button', { name: 'Add gateway' }));
    await waitFor(() => {
      expect(gateways.create).toHaveBeenCalledWith(
        { name: 'Traccar AF', adapter: 'TRACCAR' },
        expect.any(String),
      );
    });
    const keyDialog = await screen.findByRole('dialog', { name: 'Gateway Traccar AF created' });
    expect(within(keyDialog).getByTestId('gateway-key')).toHaveTextContent('gk_secret_123');
    expect(within(keyDialog).getByText(GATEWAY_KEY_WARNING)).toBeInTheDocument();
    expect(within(keyDialog).getByRole('button', { name: 'Copy key' })).toBeInTheDocument();
    await user.click(within(keyDialog).getByRole('button', { name: 'I have stored the key' }));
    await waitFor(() => {
      expect(screen.queryByText('gk_secret_123')).not.toBeInTheDocument();
    });
  });

  it('deactivates with a reason and passes the show-inactive flag', async () => {
    const user = userEvent.setup();
    gateways.deactivate.mockResolvedValue({ ...GATEWAY, active: false });
    await openGateways(user);
    expect(gateways.list).toHaveBeenLastCalledWith(expect.any(AbortSignal), false);
    await user.click(screen.getByRole('switch', { name: 'Show inactive' }));
    await waitFor(() => {
      expect(gateways.list).toHaveBeenLastCalledWith(expect.any(AbortSignal), true);
    });
    await user.click(await screen.findByRole('button', { name: 'Actions for gateway Traccar EU' }));
    await user.click(screen.getByRole('menuitem', { name: 'Deactivate' }));
    expect(screen.getByText(/key stops being accepted/)).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Key leaked');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    await waitFor(() => {
      expect(gateways.deactivate.mock.calls[0]?.[1]).toEqual({ reason: 'Key leaked' });
    });
  });

  it('hides Add and lifecycle actions without gateway manage', async () => {
    const user = userEvent.setup();
    await openGateways(user, [P.platformGatewayRead]);
    expect(screen.queryByRole('button', { name: 'Add gateway' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Actions for gateway Traccar EU' }));
    expect(screen.queryByRole('menuitem', { name: 'Deactivate' })).not.toBeInTheDocument();
  });
});
