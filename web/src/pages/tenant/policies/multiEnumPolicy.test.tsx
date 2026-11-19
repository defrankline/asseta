import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { policyService } from '../../../api/services/policyService';
import type { PolicyVersionDto } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { PolicyOverrideDialog } from './PolicyOverrideDialog';
import {
  findField,
  formatPolicyValue,
  fromInputValue,
  inputError,
  toInputValue,
} from './policyFields';

const mocks = vi.hoisted(() => ({ create: vi.fn<typeof policyService.create>() }));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { create: mocks.create },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: { list: vi.fn() },
}));

const modes = findField('CUSTOMER_HOURS', 'activation_basis');
const tiles = findField('OVERSIGHT', 'hidden_dashboard_tiles');

describe('multi-select policy fields', () => {
  it('round-trips list values in option order and labels them', () => {
    if (modes === undefined || tiles === undefined) throw new Error('fields missing');
    expect(modes.kind).toBe('multiEnum');
    expect(toInputValue(modes, ['CREDIT', 'VERIFIED_PAYMENT'])).toBe('CREDIT,VERIFIED_PAYMENT');
    expect(fromInputValue(modes, 'CREDIT,VERIFIED_PAYMENT')).toEqual([
      'VERIFIED_PAYMENT',
      'CREDIT',
    ]);
    expect(formatPolicyValue(modes, ['CREDIT'])).toBe('Approved credit');
    expect(formatPolicyValue(tiles, [])).toBe('None');
    expect(fromInputValue(tiles, '')).toEqual([]);
  });

  it('requires at least one value unless the field allows none', () => {
    if (modes === undefined || tiles === undefined) throw new Error('fields missing');
    expect(inputError(modes, '')).toBe('Choose at least 1 value');
    expect(inputError(modes, 'CREDIT')).toBeNull();
    expect(inputError(modes, 'BOGUS')).toBe('Choose from the listed values');
    expect(inputError(tiles, '')).toBeNull();
  });

  it('edits what CUSTOMER_HOURS activate from with checkboxes and sends a list', async () => {
    const user = userEvent.setup();
    const created: PolicyVersionDto = {
      id: 'v1',
      policy_type: 'CUSTOMER_HOURS',
      scope: 'TENANT',
      scope_ref_id: null,
      version: 2,
      effective_from: '2026-10-21T00:00:00Z',
      values: { activation_basis: ['VERIFIED_PAYMENT'] },
      reason: 'No credit',
      created_at: '2026-10-21T00:00:00Z',
    };
    mocks.create.mockResolvedValue(created);
    renderWithProviders(
      <PolicyOverrideDialog
        policyType="CUSTOMER_HOURS"
        initialScope="TENANT"
        initialMachine={null}
        initialSiteId=""
        current={{ activation_basis: ['VERIFIED_PAYMENT', 'CREDIT'] }}
        sites={[]}
        timeZone="UTC"
        onClose={vi.fn()}
        onCreated={vi.fn()}
      />,
      { tenantPermissions: ['tenant.policy.read', 'tenant.policy.manage'] },
    );
    await user.type(screen.getByLabelText(/^Reason/), 'No credit');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByLabelText('Override Hours activate from'));
    const credit = screen.getByRole('checkbox', { name: 'Approved credit' });
    expect(credit).toBeChecked();
    await user.click(credit);
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith(
        'CUSTOMER_HOURS',
        expect.objectContaining({ values: { activation_basis: ['VERIFIED_PAYMENT'] } }),
        expect.any(String),
      );
    });
  });
});
