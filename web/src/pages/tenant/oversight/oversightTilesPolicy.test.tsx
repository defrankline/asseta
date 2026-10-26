import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { CAPABILITY } from '../../../access/capabilities';
import type { AccountabilitySummaryDto } from '../../../api/custodyTypes';
import type { policyService } from '../../../api/services/policyService';
import type { PolicyVersionDto } from '../../../api/types';
import { notificationTargetPath } from '../../../notifications/center/display';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { buildTiles } from '../accountability/accountabilityModel';
import { PolicyOverrideDialog } from '../policies/PolicyOverrideDialog';
import {
  findField,
  formatPolicyValue,
  fromInputValue,
  inputError,
  toInputValue,
} from '../policies/policyFields';

const mocks = vi.hoisted(() => ({ createPolicy: vi.fn<typeof policyService.create>() }));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { create: mocks.createPolicy },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: { list: vi.fn() },
}));

describe('dashboard tiles and notifications', () => {
  const SUMMARY = {
    as_of: '2026-10-26T12:00:00Z',
    policy_version: 'v1',
    hidden_tiles: [],
    unavailable_tiles: [],
    disabled_capabilities: [],
    unbilled_work: {
      count: 2,
      after_days: 7,
      amounts: [{ currency: 'TZS', count: 1, amount: '2000000' }],
      oldest_days: 16,
      items: [],
    },
    idle_machines: {
      count: 1,
      after_days: 14,
      longest_idle_days: 25,
      items: [{ machine_id: 'm3', idle_since: '', idle_days: 25, planned_job_id: 'j8' }],
    },
  } as unknown as AccountabilitySummaryDto;

  it('builds the unbilled work and idle machines tiles linking to their lists', () => {
    const tiles = buildTiles(SUMMARY, () => true);
    const unbilled = tiles.find((t) => t.key === 'unbilled_work');
    expect(unbilled?.value).toBe(2);
    expect(unbilled?.to).toBe('/tenant/unbilled-work');
    expect(unbilled?.description).toBe('Oldest 16 days');
    const idle = tiles.find((t) => t.key === 'idle_machines');
    expect(idle?.to).toBe('/tenant/idle-machines');
    expect(idle?.rows?.find((r) => r.key === 'planned')?.value).toBe(1);
  });

  it('drops the tiles while their capability is off', () => {
    const off = {
      ...SUMMARY,
      disabled_capabilities: [CAPABILITY.unbilledWork, CAPABILITY.idleMachines],
    };
    const keys = buildTiles(off, () => true).map((t) => t.key);
    expect(keys).not.toContain('unbilled_work');
    expect(keys).not.toContain('idle_machines');
  });

  it('opens the job from an UNBILLED_WORK notification', () => {
    expect(notificationTargetPath(null, { kind: 'JOB', record_id: 'j1' })).toBe('/tenant/jobs/j1');
  });
});

describe('check-in times policy field', () => {
  const times = findField('OVERSIGHT', 'site_checkin_times');

  it('round-trips a sorted list of times', () => {
    if (times === undefined) throw new Error('field missing');
    expect(times.kind).toBe('timeList');
    expect(toInputValue(times, ['15:00:00', '09:30:00'])).toBe('15:00,09:30');
    expect(fromInputValue(times, '15:00,09:30,15:00')).toEqual(['09:30:00', '15:00:00']);
    expect(fromInputValue(times, '')).toEqual([]);
    expect(formatPolicyValue(times, ['09:30:00'])).toBe('09:30');
    expect(formatPolicyValue(times, [])).toBe('None');
    expect(inputError(times, '09:30,25:00')).toBe('Use HH:MM (24 h) for every time');
    expect(inputError(times, '')).toBeNull();
  });

  it('adds and removes times and sends the list', async () => {
    const user = userEvent.setup();
    const created: PolicyVersionDto = {
      id: 'v1',
      policy_type: 'OVERSIGHT',
      scope: 'TENANT',
      scope_ref_id: null,
      version: 2,
      effective_from: '2026-10-26T00:00:00Z',
      values: { site_checkin_times: ['07:30:00', '12:00:00'] },
      reason: 'Check-in times',
      created_at: '2026-10-26T00:00:00Z',
    };
    mocks.createPolicy.mockResolvedValue(created);
    renderWithProviders(
      <PolicyOverrideDialog
        policyType="OVERSIGHT"
        initialScope="TENANT"
        initialMachine={null}
        initialSiteId=""
        current={{ site_checkin_times: ['12:00:00', '16:00:00'] }}
        sites={[]}
        timeZone="UTC"
        onClose={vi.fn()}
        onCreated={vi.fn()}
      />,
      { tenantPermissions: ['tenant.policy.read', 'tenant.policy.manage'] },
    );
    await user.type(screen.getByLabelText(/^Reason/), 'Check-in times');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByLabelText('Override Check-in times'));
    const group = screen.getByRole('group', { name: 'Check-in times' });
    await user.type(within(group).getByLabelText('Add a time (HH:MM)'), '7:30');
    expect(within(group).getByRole('button', { name: 'Add time' })).toBeDisabled();
    await user.clear(within(group).getByLabelText('Add a time (HH:MM)'));
    await user.type(within(group).getByLabelText('Add a time (HH:MM)'), '07:30');
    await user.click(within(group).getByRole('button', { name: 'Add time' }));
    const sixteen = within(group).getByRole('button', { name: 'Time 16:00' });
    await user.click(within(sixteen).getByTestId('CancelIcon'));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Create version' }));
    await waitFor(() => {
      expect(mocks.createPolicy).toHaveBeenCalledWith(
        'OVERSIGHT',
        expect.objectContaining({ values: { site_checkin_times: ['07:30:00', '12:00:00'] } }),
        expect.any(String),
      );
    });
  });
});
