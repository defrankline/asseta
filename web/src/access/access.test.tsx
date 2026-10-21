import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { NO_MODE, type ConsoleMode } from '../session/permissions';
import { SessionContext, type SessionContextValue } from '../session/SessionContext';
import { makeMe, makeSession, TENANT_A } from '../test/fixtures';
import { Can } from './Can';
import { RequirePermission } from './RequirePermission';

const platformMe = makeMe({ platform_permissions: ['platform.system.read'] });

function withSession(session: SessionContextValue, ui: ReactNode) {
  return render(<SessionContext.Provider value={session}>{ui}</SessionContext.Provider>);
}

function guarded(session: SessionContextValue, permission: string | string[]) {
  return withSession(
    session,
    <MemoryRouter initialEntries={['/secret']}>
      <Routes>
        <Route
          path="/secret"
          element={
            <RequirePermission permission={permission}>
              <p>secret content</p>
            </RequirePermission>
          }
        />
        <Route path="/403" element={<p>forbidden page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('<Can>', () => {
  const cases: [string, SessionContextValue, string | string[]][] = [
    ['no session data', makeSession(null, NO_MODE), 'platform.system.read'],
    ['permission missing', makeSession(platformMe, { kind: 'platform' }), 'platform.tenant.write'],
    ['empty requirement', makeSession(platformMe, { kind: 'platform' }), []],
    [
      'platform code in tenant mode',
      makeSession(platformMe, { kind: 'tenant', tenantId: TENANT_A }),
      'platform.system.read',
    ],
    [
      'session still loading',
      makeSession(platformMe, { kind: 'platform' }, 'loading'),
      'platform.system.read',
    ],
  ];

  it.each(cases)('denies when %s', (_name, session, permission) => {
    withSession(
      session,
      <Can permission={permission} fallback={<span>denied</span>}>
        <span>allowed</span>
      </Can>,
    );
    expect(screen.queryByText('allowed')).not.toBeInTheDocument();
    expect(screen.getByText('denied')).toBeInTheDocument();
  });

  it('renders children when granted', () => {
    withSession(
      makeSession(platformMe, { kind: 'platform' }),
      <Can permission="platform.system.read">
        <span>allowed</span>
      </Can>,
    );
    expect(screen.getByText('allowed')).toBeInTheDocument();
  });
});

describe('<RequirePermission>', () => {
  it('redirects to 403 by default when not granted', () => {
    guarded(makeSession(makeMe(), { kind: 'tenant', tenantId: TENANT_A }), 'tenant.machine.write');
    expect(screen.getByText('forbidden page')).toBeInTheDocument();
    expect(screen.queryByText('secret content')).not.toBeInTheDocument();
  });

  it('denies when there is no mode selected', () => {
    const mode: ConsoleMode = NO_MODE;
    guarded(makeSession(platformMe, mode), 'platform.system.read');
    expect(screen.getByText('forbidden page')).toBeInTheDocument();
  });

  it('shows a loader (not content) while the session loads', () => {
    guarded(makeSession(platformMe, { kind: 'platform' }, 'loading'), 'platform.system.read');
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByText('secret content')).not.toBeInTheDocument();
  });

  it('renders content when all permissions are granted', () => {
    guarded(makeSession(platformMe, { kind: 'platform' }), ['platform.system.read']);
    expect(screen.getByText('secret content')).toBeInTheDocument();
  });
});
