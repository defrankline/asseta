import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { platformMlService } from '../../../api/services/platformMlService';
import type { tenantService } from '../../../api/services/tenantService';
import type { TenantDto } from '../../../api/types';
import { page } from '../../../test/financeFixtures';
import { TENANT_A } from '../../../test/fixtures';
import { makeModel, makeReadiness, MODEL_ID, SETTINGS_ON } from '../../../test/mlFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ModelsPage } from './ModelsPage';
import { SWITCH_OFF_EFFECT } from './InferenceSwitchCard';

const mocks = vi.hoisted(() => ({
  listModels: vi.fn<typeof platformMlService.listModels>(),
  listReadiness: vi.fn<typeof platformMlService.listReadiness>(),
  getSettings: vi.fn<typeof platformMlService.getSettings>(),
  updateSettings: vi.fn<typeof platformMlService.updateSettings>(),
  runSnapshots: vi.fn<typeof platformMlService.runSnapshots>(),
  runTraining: vi.fn<typeof platformMlService.runTraining>(),
  listTenants: vi.fn<typeof tenantService.list>(),
  getTenant: vi.fn<typeof tenantService.get>(),
}));
vi.mock('../../../api/services/platformMlService', () => ({
  platformMlService: {
    listModels: mocks.listModels,
    listReadiness: mocks.listReadiness,
    getSettings: mocks.getSettings,
    updateSettings: mocks.updateSettings,
    runSnapshots: mocks.runSnapshots,
    runTraining: mocks.runTraining,
  },
}));
vi.mock('../../../api/services/tenantService', () => ({
  tenantService: { list: mocks.listTenants, get: mocks.getTenant },
}));

const ACME: TenantDto = {
  id: TENANT_A,
  legal_name: 'Acme Plant Hire Ltd',
  display_name: 'Acme Plant Hire',
  registration_number: null,
  contact_name: 'Owner',
  contact_email: 'owner@acme.test',
  contact_phone: null,
  status: 'ACTIVE',
  access_state: 'FULL',
  access_state_reason: null,
  verification_status: 'VERIFIED',
  created_at: '2026-01-01T00:00:00Z',
  version: 1,
};

const READ = [P.platformMlRead];
const MANAGE = [P.platformMlRead, P.platformMlManage];

beforeEach(() => {
  mocks.listModels.mockResolvedValue(page([makeModel()]));
  mocks.listReadiness.mockResolvedValue(page([makeReadiness()]));
  mocks.getSettings.mockResolvedValue(SETTINGS_ON);
  mocks.updateSettings.mockResolvedValue({
    ...SETTINGS_ON,
    inference_enabled: false,
    lock_version: 1,
  });
  mocks.listTenants.mockResolvedValue(page([ACME]));
  mocks.getTenant.mockResolvedValue(ACME);
});
afterEach(() => {
  vi.clearAllMocks();
});

function renderPage(permissions: string[]) {
  renderWithProviders(
    <Routes>
      <Route path="/platform/models" element={<ModelsPage />} />
      <Route path="/platform/models/:modelId" element={<p>Model page</p>} />
    </Routes>,
    { permissions, route: '/platform/models' },
  );
}

describe('ModelsPage', () => {
  it('lists model versions and opens one from its row', async () => {
    const user = userEvent.setup();
    renderPage(READ);
    const row = (await screen.findByText('machine_week_anomaly v3')).closest('tr') as HTMLElement;
    expect(within(row).getByText('Evaluated')).toBeInTheDocument();
    expect(within(row).getByText('Passed')).toBeInTheDocument();
    expect(within(row).getByText('Isolation forest')).toBeInTheDocument();
    await user.click(row);
    expect(await screen.findByText('Model page')).toBeInTheDocument();
  });

  it('filters versions by a server-searched tenant, status and name', async () => {
    const user = userEvent.setup();
    renderPage(READ);
    await screen.findByText('machine_week_anomaly v3');
    const versions = screen.getByRole('region', { name: 'Model versions' });
    const picker = within(versions).getByRole('combobox', { name: 'Tenant' });
    await user.click(picker);
    await user.type(picker, 'acm');
    await waitFor(() => {
      expect(mocks.listTenants).toHaveBeenCalledWith(
        expect.objectContaining({ q: 'acm' }),
        expect.any(AbortSignal),
      );
    });
    await user.click(await screen.findByRole('option', { name: 'Acme Plant Hire' }));
    await waitFor(() => {
      expect(mocks.listModels.mock.lastCall?.[0].filters?.tenant_id).toBe(TENANT_A);
    });
    await user.click(within(versions).getByRole('combobox', { name: 'Status' }));
    await user.click(await screen.findByRole('option', { name: 'Deployed (shadow)' }));
    await waitFor(() => {
      expect(mocks.listModels.mock.lastCall?.[0].filters?.status).toBe('DEPLOYED_SHADOW');
    });
    await user.type(within(versions).getByRole('textbox', { name: 'Model name' }), 'machine');
    await waitFor(() => {
      expect(mocks.listModels.mock.lastCall?.[0].filters?.name).toBe('machine');
    });
  });

  it('switches inference off only with a reason, after confirming, sending the version read', async () => {
    const user = userEvent.setup();
    renderPage(MANAGE);
    const card = await screen.findByRole('region', { name: 'Inference switch' });
    expect(await within(card).findByText('Inference on')).toBeInTheDocument();
    await user.click(within(card).getByRole('button', { name: 'Switch inference off' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(SWITCH_OFF_EFFECT)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Switch off' }));
    expect(await within(dialog).findByText('A reason is required')).toBeInTheDocument();
    expect(mocks.updateSettings).not.toHaveBeenCalled();
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'Incident review');
    await user.click(within(dialog).getByRole('button', { name: 'Switch off' }));
    await waitFor(() => {
      expect(mocks.updateSettings).toHaveBeenCalledWith(
        { inference_enabled: false, reason: 'Incident review', lock_version: 0 },
        expect.any(String),
      );
    });
  });

  it('runs training for a tenant and summarises the new version', async () => {
    const user = userEvent.setup();
    mocks.runTraining.mockResolvedValue({
      readiness: makeReadiness({ status: 'READY', reasons: [] }),
      model: makeModel({ version: 4, id: MODEL_ID }),
    });
    renderPage(MANAGE);
    const readiness = await screen.findByRole('region', { name: 'Readiness per tenant' });
    const row = (await within(readiness).findByText('Acme Plant Hire')).closest(
      'tr',
    ) as HTMLElement;
    expect(within(row).getByText('Not enough history')).toBeInTheDocument();
    expect(within(row).getByText(/at least 5 required/)).toBeInTheDocument();
    await user.click(within(row).getByRole('button', { name: 'Train now' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/never deployed automatically/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Train now' }));
    await waitFor(() => {
      expect(mocks.runTraining).toHaveBeenCalledWith(TENANT_A, expect.any(String));
    });
    expect(await screen.findByText(/Trained machine_week_anomaly version 4/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open the new version' })).toHaveAttribute(
      'href',
      `/platform/models/${MODEL_ID}`,
    );
  });

  it('refreshes snapshots for a tenant with a bounded period', async () => {
    const user = userEvent.setup();
    mocks.runSnapshots.mockResolvedValue({
      run_id: 'r',
      tenant_id: TENANT_A,
      week_ends: ['a', 'b'],
      machines: 6,
      written: 12,
      skipped_existing: 3,
      skipped_future: 0,
    });
    renderPage(MANAGE);
    const readiness = await screen.findByRole('region', { name: 'Readiness per tenant' });
    const row = (await within(readiness).findByText('Acme Plant Hire')).closest(
      'tr',
    ) as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Refresh snapshots' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Refresh snapshots' }));
    await waitFor(() => {
      expect(mocks.runSnapshots).toHaveBeenCalled();
    });
    const [tenantArg, body] = mocks.runSnapshots.mock.lastCall ?? [];
    expect(tenantArg).toBe(TENANT_A);
    expect(body?.from_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(body !== undefined && body.from_date <= body.to_date).toBe(true);
    expect(await screen.findByText(/12 written across 2 weeks and 6 machines/)).toBeInTheDocument();
  });

  it('shows no switch or run buttons to read-only (auditor) users', async () => {
    renderPage(READ);
    const card = await screen.findByRole('region', { name: 'Inference switch' });
    expect(await within(card).findByText('Inference on')).toBeInTheDocument();
    await screen.findByText('machine_week_anomaly v3');
    expect(screen.queryByRole('button', { name: /Switch inference/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Train now/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Refresh snapshots/ })).not.toBeInTheDocument();
  });
});
