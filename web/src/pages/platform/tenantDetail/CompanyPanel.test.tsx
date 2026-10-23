import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { TenantDto } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { CompanyPanel } from './CompanyPanel';

function tenant(verification: TenantDto['verification_status']): TenantDto {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    legal_name: 'Wambura & Sons Ltd',
    display_name: 'Wambura & Sons Ltd',
    contact_name: 'Owner',
    contact_email: 'owner@example.com',
    status: 'ACTIVE',
    verification_status: verification,
    access_state: 'FULL',
    created_at: '2026-10-23T14:38:00Z',
  } as TenantDto;
}

describe('CompanyPanel', () => {
  it.each([
    ['UNVERIFIED', 'Verify company'],
    ['VERIFIED', 'Change verification'],
  ] as const)('labels the verification action for a %s company', (status, label) => {
    renderWithProviders(<CompanyPanel tenant={tenant(status)} onChanged={() => undefined} />, {
      permissions: [P.platformTenantRead, P.platformTenantVerify],
    });
    expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
  });
});
