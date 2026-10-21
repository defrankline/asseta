import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { policyService } from '../../../api/services/policyService';
import type { JobSiteDto, PolicyType, PolicyVersionDto } from '../../../api/types';
import { MACHINE } from '../../../test/jobFixtures';
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
  opening_mode: 'AUTOMATIC',
  closing_mode: 'AUTOMATIC',
  manual_photo_required: true,
  max_hours_per_elapsed_hour: '1.05',
  billable_hours_increment: '0.1',
  rounding: 'HALF_UP',
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

describe('PolicyOverrideDialog · METER_CAPTURE / HIRE_BILLING', () => {
  it('sets opening and closing modes independently', async () => {
    const user = userEvent.setup();
    mocks.create.mockResolvedValue(version);
    open('METER_CAPTURE', 'TENANT');
    await toValues(user);
    expect(screen.getAllByRole('switch')).toHaveLength(14);
    await user.click(await screen.findByLabelText('Override Opening reading mode'));
    await user.click(screen.getByLabelText('Override Closing reading mode'));
    await choose(user, 'Opening reading mode', 'Manual (numeric entry)');
    expect(screen.getByRole('combobox', { name: 'Closing reading mode' })).toHaveTextContent(
      'Automatic',
    );
    await user.click(screen.getByLabelText('Override Max meter hours per elapsed hour'));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Create version' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith(
        'METER_CAPTURE',
        expect.objectContaining({
          scope: 'TENANT',
          values: {
            opening_mode: 'MANUAL',
            closing_mode: 'AUTOMATIC',
            max_hours_per_elapsed_hour: '1.05',
          },
        }),
        expect.any(String),
      );
    });
  });

  it('limits machine overrides to the six machine fields', async () => {
    const user = userEvent.setup();
    open('METER_CAPTURE', 'MACHINE');
    await toValues(user);
    await screen.findByLabelText('Override Opening reading mode');
    const labels = screen.getAllByRole('switch').map((s) => s.getAttribute('aria-label'));
    expect(labels).toEqual([
      'Override Opening reading mode',
      'Override Closing reading mode',
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

  it('offers HIRE_BILLING at tenant scope only, with increment and rounding', async () => {
    const user = userEvent.setup();
    mocks.create.mockResolvedValue({ ...version, policy_type: 'HIRE_BILLING' });
    open('HIRE_BILLING', 'MACHINE');
    await user.click(screen.getByRole('combobox', { name: 'Scope' }));
    const listbox = await screen.findByRole('listbox');
    expect(
      within(listbox)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Tenant default (all fields)']);
    await user.keyboard('{Escape}');
    await toValues(user);
    expect(screen.getAllByRole('switch')).toHaveLength(2);
    await user.click(screen.getByLabelText('Override Rounding'));
    await choose(user, 'Rounding', 'Up');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Create version' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith(
        'HIRE_BILLING',
        expect.objectContaining({
          scope: 'TENANT',
          scope_ref_id: null,
          values: { rounding: 'UP' },
        }),
        expect.any(String),
      );
    });
  });
});
