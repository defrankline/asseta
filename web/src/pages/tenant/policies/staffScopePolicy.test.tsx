import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { policyService } from '../../../api/services/policyService';
import type { PolicyVersionDto } from '../../../api/types';
import { SUPERVISOR } from '../../../test/financeFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { PolicyOverrideDialog } from './PolicyOverrideDialog';
import { allowedFields, scopesFor } from './policyFields';

const mocks = vi.hoisted(() => ({ create: vi.fn<typeof policyService.create>() }));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { create: mocks.create },
}));
vi.mock('../../../api/services/staffService', async () => {
  const { SUPERVISOR: s } = await import('../../../test/financeFixtures');
  return {
    staffService: {
      get: vi.fn().mockResolvedValue(s),
      list: vi.fn().mockResolvedValue({ items: [s], total: 1, page: 1, page_size: 20 }),
    },
  };
});

describe('cash holding allowance (CASH_CUSTODY site / staff overrides)', () => {
  it('lets only max_holding_days vary by site or staff member', () => {
    expect(scopesFor('CASH_CUSTODY')).toEqual(['TENANT', 'SITE', 'STAFF']);
    expect(allowedFields('CASH_CUSTODY', 'STAFF').map((f) => f.key)).toEqual(['max_holding_days']);
    expect(allowedFields('CASH_CUSTODY', 'SITE').map((f) => f.key)).toEqual(['max_holding_days']);
    expect(scopesFor('TRACKING')).not.toContain('STAFF');
    const keys = allowedFields('CASH_CUSTODY', 'TENANT').map((f) => f.key);
    expect(keys).toEqual(
      expect.arrayContaining([
        'remittance_reference_required',
        'remittance_evidence_required',
        'remittance_account_required',
        'max_holding_days',
      ]),
    );
  });

  it("creates a staff member's own allowance", async () => {
    const user = userEvent.setup();
    const created: PolicyVersionDto = {
      id: 'v9',
      policy_type: 'CASH_CUSTODY',
      scope: 'STAFF',
      scope_ref_id: SUPERVISOR.id,
      version: 3,
      effective_from: '2026-10-26T00:00:00Z',
      values: { max_holding_days: 5 },
      reason: 'Remote site',
      created_at: '2026-10-26T00:00:00Z',
    };
    mocks.create.mockResolvedValue(created);
    renderWithProviders(
      <PolicyOverrideDialog
        policyType="CASH_CUSTODY"
        initialScope="STAFF"
        initialMachine={null}
        initialSiteId=""
        initialStaffId={SUPERVISOR.id}
        current={{ enabled: true, max_holding_days: 2 }}
        sites={[]}
        timeZone="UTC"
        onClose={vi.fn()}
        onCreated={vi.fn()}
      />,
      { tenantPermissions: ['tenant.policy.read', 'tenant.policy.manage', 'tenant.staff.read'] },
    );
    expect(await screen.findByDisplayValue(SUPERVISOR.full_name)).toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Reason/), 'Remote site');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(
      await screen.findByLabelText('Override Days a custodian may hold unremitted cash'),
    );
    expect(screen.getAllByRole('switch')).toHaveLength(1);
    const input = screen.getByLabelText('Days a custodian may hold unremitted cash (days)');
    expect(input).toHaveValue('2');
    await user.clear(input);
    await user.type(input, '5');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Staff member override')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create version' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith(
        'CASH_CUSTODY',
        {
          scope: 'STAFF',
          scope_ref_id: SUPERVISOR.id,
          values: { max_holding_days: 5 },
          reason: 'Remote site',
          effective_from: null,
        },
        expect.any(String),
      );
    });
  });
});
