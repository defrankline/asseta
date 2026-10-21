import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { staffService } from '../../../api/services/staffService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { CreateStaffDialog } from './CreateStaffDialog';

const mocks = vi.hoisted(() => ({ create: vi.fn<typeof staffService.create>() }));
vi.mock('../../../api/services/staffService', () => ({ staffService: mocks }));

describe('CreateStaffDialog', () => {
  it('reviews and creates a staff member with nulls for empty optionals', async () => {
    const user = userEvent.setup();
    mocks.create.mockResolvedValue({
      id: 's1',
      full_name: 'Asha Mwita',
      kind: 'OPERATOR',
      employee_code: null,
      phone: null,
      keycloak_subject: null,
      is_active: true,
      deactivated_at: null,
      deactivation_reason: null,
      version: 1,
    });
    const onCreated = vi.fn();
    renderWithProviders(<CreateStaffDialog onClose={vi.fn()} onCreated={onCreated} />, {
      tenantPermissions: ['tenant.staff.write'],
    });
    await user.type(screen.getByRole('textbox', { name: /Full name/ }), 'Asha Mwita');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await screen.findByRole('textbox', { name: /Login subject/ });
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Not linked')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create staff member' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith(
        {
          full_name: 'Asha Mwita',
          kind: 'OPERATOR',
          employee_code: null,
          phone: null,
          keycloak_subject: null,
          is_active: true,
        },
        expect.any(String),
      );
    });
    expect(onCreated).toHaveBeenCalled();
  });
});
