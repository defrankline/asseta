import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../access/permissionCodes';
import { SessionContext } from '../session/SessionContext';
import { makeMe, makeSession, TENANT_A } from '../test/fixtures';
import { LoginRedirectPage } from '../pages/LoginRedirectPage';
import { TenantAccessBanner } from './TenantAccessBanner';

const login = vi.fn();
vi.mock('../auth/useAuth', () => ({ useAuth: () => ({ login }) }));

const REASON = 'Company closure requested: all its data will be deleted on 2026-12-12';

function renderBanner(permissions: string[], reason: string | null) {
  const base = makeMe();
  const me = {
    ...base,
    tenants: base.tenants.map((t) => ({
      ...t,
      permissions,
      access_state: 'READ_ONLY' as const,
      access_state_reason: reason,
    })),
  };
  render(
    <SessionContext.Provider value={makeSession(me, { kind: 'tenant', tenantId: TENANT_A })}>
      <MemoryRouter>
        <TenantAccessBanner />
      </MemoryRouter>
    </SessionContext.Provider>,
  );
}

describe('TenantAccessBanner', () => {
  it('shows the server reason for read-only access, with a link for those who may close', () => {
    renderBanner([P.tenantCompanyClose], REASON);
    expect(screen.getByText(/Tenant A is read-only/)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(REASON))).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See Close company' })).toHaveAttribute(
      'href',
      '/tenant/company/close',
    );
  });

  it('shows the reason without a link to others', () => {
    renderBanner([], REASON);
    expect(screen.getByText(new RegExp(REASON))).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('keeps the subscription wording when there is no reason', () => {
    renderBanner([], null);
    expect(screen.getByText(/until the subscription is restored/)).toBeInTheDocument();
  });
});

describe('LoginRedirectPage after an account deletion', () => {
  it('shows the message and waits instead of redirecting', () => {
    render(
      <MemoryRouter initialEntries={['/signed-out?reason=account-deleted']}>
        <LoginRedirectPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Your account was deleted/)).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it('redirects to sign-in otherwise', () => {
    render(
      <MemoryRouter initialEntries={['/tenant/jobs']}>
        <LoginRedirectPage />
      </MemoryRouter>,
    );
    expect(login).toHaveBeenCalled();
  });
});
