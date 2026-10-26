import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { policyService } from '../../../api/services/policyService';
import { policyVersionSchema } from '../../../api/services/geoSchemas';
import type { CategoryDto, PolicyVersionDto } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { PolicyOverrideDialog } from './PolicyOverrideDialog';
import { PolicyVersionsTable } from './PolicyVersionsTable';
import { allowedFields, scopesFor } from './policyFields';

const CATEGORY = {
  id: 'cat-1',
  name: 'Excavators',
  is_active: true,
} as CategoryDto;

const mocks = vi.hoisted(() => ({ create: vi.fn<typeof policyService.create>() }));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { create: mocks.create },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: {
    listCategories: vi.fn().mockResolvedValue([{ id: 'cat-1', name: 'Excavators' }]),
    getCategory: vi.fn().mockResolvedValue({ id: 'cat-1', name: 'Excavators' }),
  },
}));

const VERSION: PolicyVersionDto = {
  id: 'v9',
  policy_type: 'FRAUD_CONTROLS',
  scope: 'MACHINE_CATEGORY',
  scope_ref_id: CATEGORY.id,
  version: 4,
  effective_from: '2026-10-26T00:00:00Z',
  values: { fuel_litres_per_hour_max: '18' },
  reason: 'Excavator norm',
  created_at: '2026-10-26T00:00:00Z',
};

describe('fuel norm per machine category (FRAUD_CONTROLS MACHINE_CATEGORY scope)', () => {
  it('lets only the fuel norm vary by machine category', () => {
    expect(scopesFor('FRAUD_CONTROLS')).toEqual(['TENANT', 'MACHINE_CATEGORY', 'MACHINE']);
    expect(allowedFields('FRAUD_CONTROLS', 'MACHINE_CATEGORY').map((f) => f.key)).toEqual([
      'fuel_litres_per_hour_max',
    ]);
    expect(scopesFor('CASH_CUSTODY')).not.toContain('MACHINE_CATEGORY');
    expect(policyVersionSchema.isValidSync(VERSION)).toBe(true);
  });

  it('creates a category version picked with the category search', async () => {
    const user = userEvent.setup();
    mocks.create.mockResolvedValue(VERSION);
    renderWithProviders(
      <PolicyOverrideDialog
        policyType="FRAUD_CONTROLS"
        initialScope="MACHINE_CATEGORY"
        initialMachine={null}
        initialSiteId=""
        current={{ fuel_litres_per_hour_max: null }}
        sites={[]}
        timeZone="UTC"
        onClose={vi.fn()}
        onCreated={vi.fn()}
      />,
      { tenantPermissions: ['tenant.policy.read', 'tenant.policy.manage'] },
    );
    await user.click(screen.getByLabelText(/^Machine category/));
    await user.click(await screen.findByRole('option', { name: 'Excavators' }));
    await user.type(screen.getByLabelText(/^Reason/), 'Excavator norm');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByLabelText('Override Fuel norm per engine hour'));
    expect(screen.getAllByRole('switch')).toHaveLength(1);
    await user.type(screen.getByLabelText('Fuel norm per engine hour (L per engine hour)'), '18');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Machine category override')).toBeInTheDocument();
    expect(screen.getByText('Excavators')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create version' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith(
        'FRAUD_CONTROLS',
        {
          scope: 'MACHINE_CATEGORY',
          scope_ref_id: 'cat-1',
          values: { fuel_litres_per_hour_max: '18' },
          reason: 'Excavator norm',
          effective_from: null,
        },
        expect.any(String),
      );
    });
  });

  it('names the category in the version history', async () => {
    renderWithProviders(
      <PolicyVersionsTable versions={[VERSION]} timeZone="UTC" refLabel={(id) => id} />,
      { tenantPermissions: ['tenant.policy.read'] },
    );
    expect(await screen.findByText('Excavators')).toBeInTheDocument();
  });
});
