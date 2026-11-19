import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { policyService } from '../../../api/services/policyService';
import type { JobSiteDto, PolicyType, PolicyVersionDto } from '../../../api/types';
import { MACHINE } from '../../../test/meterFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { PolicyOverrideDialog } from './PolicyOverrideDialog';
import type { OverrideScope } from './policyFields';

const mocks = vi.hoisted(() => ({ create: vi.fn<typeof policyService.create>() }));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { create: mocks.create },
}));
vi.mock('../../../api/services/machineService', () => ({ machineService: { list: vi.fn() } }));

const SITE: JobSiteDto = {
  id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  code: 'S1',
  name: 'Site One',
  address: null,
  center: { type: 'Point', coordinates: [39.2, -6.8] },
  is_active: true,
  version: 1,
};
const CURRENT = {
  capture_mode: 'AUTOMATIC',
  manual_photo_required: true,
  max_hours_per_elapsed_hour: '1.05',
  offline_grant_hours: 72,
};

function open(policyType: PolicyType, scope: OverrideScope) {
  renderWithProviders(
    <PolicyOverrideDialog
      policyType={policyType}
      initialScope={scope}
      initialMachine={scope === 'MACHINE' ? MACHINE : null}
      initialSiteId={scope === 'SITE' ? SITE.id : ''}
      current={CURRENT}
      sites={[SITE]}
      timeZone="UTC"
      onClose={vi.fn()}
      onCreated={vi.fn()}
    />,
    { tenantPermissions: ['tenant.policy.read', 'tenant.policy.manage'] },
  );
}

async function toValues(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/^Reason/), 'Manual closing at quarry');
  await user.click(screen.getByRole('button', { name: 'Next' }));
}

async function choose(user: ReturnType<typeof userEvent.setup>, label: string, option: string) {
  await user.click(screen.getByRole('combobox', { name: label }));
  await user.click(await screen.findByRole('option', { name: option }));
}

const version: PolicyVersionDto = {
  id: 'v1',
  policy_type: 'METER_CAPTURE',
  scope: 'TENANT',
  scope_ref_id: null,
  version: 1,
  effective_from: '2026-10-21T00:00:00Z',
  values: {},
  reason: 'r',
  created_at: '2026-10-21T00:00:00Z',
};

describe('PolicyOverrideDialog · METER_CAPTURE / DEVICE_SYNC', () => {
  it('sets the one reading mode', async () => {
    const user = userEvent.setup();
    mocks.create.mockResolvedValue(version);
    open('METER_CAPTURE', 'TENANT');
    await toValues(user);
    expect(screen.getAllByRole('switch')).toHaveLength(13);
    await user.click(await screen.findByLabelText('Override Reading mode'));
    await choose(user, 'Reading mode', 'Manual (numeric entry)');
    await user.click(screen.getByLabelText('Override Max meter hours per elapsed hour'));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith(
        'METER_CAPTURE',
        expect.objectContaining({
          scope: 'TENANT',
          values: {
            capture_mode: 'MANUAL',
            max_hours_per_elapsed_hour: '1.05',
          },
        }),
        expect.any(String),
      );
    });
  });

  it('limits machine overrides to the five machine fields', async () => {
    const user = userEvent.setup();
    open('METER_CAPTURE', 'MACHINE');
    await toValues(user);
    await screen.findByLabelText('Override Reading mode');
    const labels = screen.getAllByRole('switch').map((s) => s.getAttribute('aria-label'));
    expect(labels).toEqual([
      'Override Reading mode',
      'Override Photo required for manual readings',
      'Override Minimum OCR confidence',
      'Override Max meter hours per elapsed hour',
      'Override Telemetry engine-hours tolerance',
    ]);
  });

  it('limits site overrides to GPS accuracy and tracker distance', async () => {
    const user = userEvent.setup();
    open('METER_CAPTURE', 'SITE');
    await toValues(user);
    await screen.findByLabelText('Override GPS max accuracy');
    const labels = screen.getAllByRole('switch').map((s) => s.getAttribute('aria-label'));
    expect(labels).toEqual(['Override GPS max accuracy', 'Override Tracker distance tolerance']);
  });

  it('offers DEVICE_SYNC at tenant scope only', async () => {
    const user = userEvent.setup();
    mocks.create.mockResolvedValue({ ...version, policy_type: 'DEVICE_SYNC' });
    open('DEVICE_SYNC', 'MACHINE');
    await user.click(screen.getByRole('combobox', { name: 'Scope' }));
    const listbox = await screen.findByRole('listbox');
    expect(
      within(listbox)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Tenant default (all fields)']);
    await user.keyboard('{Escape}');
    await toValues(user);
    expect(screen.getAllByRole('switch')).toHaveLength(4);
    await user.click(screen.getByLabelText('Override Offline grant'));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith(
        'DEVICE_SYNC',
        expect.objectContaining({
          scope: 'TENANT',
          scope_ref_id: null,
          values: { offline_grant_hours: 72 },
        }),
        expect.any(String),
      );
    });
  });
});
