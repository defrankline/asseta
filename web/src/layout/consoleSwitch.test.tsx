import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useEffect } from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FORBIDDEN_PATH, RequirePermission } from '../access/RequirePermission';
import type { MeResponse } from '../api/types';
import { NotificationProvider } from '../notifications/NotificationProvider';
import { ROUTES } from '../navigation/routes';
import { storeMode } from '../session/modeStorage';
import { SessionProvider } from '../session/SessionProvider';
import { useSession } from '../session/useSession';
import { TENANT_A, TENANT_B } from '../test/fixtures';
import { makePlatformStaffMe, mandatedTenant } from '../test/mandateFixtures';
import { MandateBanner } from './MandateBanner';
import { SWITCHER_SEARCH_THRESHOLD, TenantSwitcher } from './TenantSwitcher';

/** Every pathname rendered, to prove the 403 page is never even flashed. */
function LocationLog({ log }: { log: string[] }) {
  const { pathname } = useLocation();
  useEffect(() => {
    log.push(pathname);
  }, [pathname, log]);
  return null;
}

function Home() {
  const { mode } = useSession();
  return <p>Home · {mode.kind === 'tenant' ? mode.tenantId : mode.kind}</p>;
}

function ReloadButton() {
  const { reload } = useSession();
  return (
    <button type="button" onClick={reload}>
      Mandate changed
    </button>
  );
}

function renderConsole(
  loadMe: (signal: AbortSignal) => Promise<MeResponse>,
  route: string,
  log: string[] = [],
) {
  render(
    <NotificationProvider>
      <MemoryRouter initialEntries={[route]}>
        <SessionProvider loadMe={loadMe}>
          <TenantSwitcher />
          <MandateBanner />
          <ReloadButton />
          <LocationLog log={log} />
          <Routes>
            <Route path={ROUTES.home} element={<Home />} />
            <Route
              path={ROUTES.platformManagedService}
              element={
                <RequirePermission permission="platform.mandate.read">
                  <p>Managed service page</p>
                </RequirePermission>
              }
            />
            <Route
              path={ROUTES.tenantMachines}
              element={
                <RequirePermission permission="tenant.machine.read">
                  <p>Machines page</p>
                </RequirePermission>
              }
            />
            <Route path={FORBIDDEN_PATH} element={<p>Forbidden</p>} />
          </Routes>
        </SessionProvider>
      </MemoryRouter>
    </NotificationProvider>,
  );
  return log;
}

beforeEach(() => {
  window.localStorage.clear();
});

describe('Switching console from a console-specific page', () => {
  it('enters a mandated client from /platform/managed-service and lands home, never on 403', async () => {
    const user = userEvent.setup();
    const log = renderConsole(
      () => Promise.resolve(makePlatformStaffMe()),
      ROUTES.platformManagedService,
    );
    expect(await screen.findByText('Managed service page')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Switch tenant/ }));
    await user.click(screen.getByRole('menuitem', { name: /Kilimo Haulage/ }));

    expect(await screen.findByText(`Home · ${TENANT_B}`)).toBeInTheDocument();
    expect(log).not.toContain(FORBIDDEN_PATH);
    expect(screen.queryByText('Forbidden')).not.toBeInTheDocument();
  });

  it('"Return to your tenant" from a client page lands home, never on 403', async () => {
    const user = userEvent.setup();
    storeMode({ kind: 'tenant', tenantId: TENANT_B });
    const log = renderConsole(() => Promise.resolve(makePlatformStaffMe()), ROUTES.tenantMachines);
    expect(await screen.findByText('Machines page')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Return to your tenant' }));

    expect(await screen.findByText('Home · platform')).toBeInTheDocument();
    expect(log).not.toContain(FORBIDDEN_PATH);
  });
});

describe('Session refresh after a mandate change', () => {
  it('lists the newly mandated client in the switcher without a page reload', async () => {
    const user = userEvent.setup();
    const loadMe = vi
      .fn<(signal: AbortSignal) => Promise<MeResponse>>()
      .mockResolvedValueOnce(makePlatformStaffMe([]))
      .mockResolvedValue(makePlatformStaffMe());
    renderConsole(loadMe, ROUTES.platformManagedService);
    expect(await screen.findByText('Managed service page')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Switch tenant/ }));
    expect(screen.queryByRole('menuitem', { name: /Kilimo Haulage/ })).not.toBeInTheDocument();
    await user.keyboard('{Escape}');

    await user.click(screen.getByRole('button', { name: 'Mandate changed' }));
    await waitFor(() => {
      expect(loadMe).toHaveBeenCalledTimes(2);
    });
    // Background refresh: the page stays mounted (no app-wide loading state).
    expect(screen.getByText('Managed service page')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Switch tenant/ }));
    expect(await screen.findByRole('menuitem', { name: /Kilimo Haulage/ })).toBeInTheDocument();
  });
});

describe('Switch tenant menu search', () => {
  it(`offers a search box above ${String(SWITCHER_SEARCH_THRESHOLD)} entries`, async () => {
    const user = userEvent.setup();
    const clients = Array.from({ length: SWITCHER_SEARCH_THRESHOLD }, (_, i) =>
      mandatedTenant({
        tenant_id: `${TENANT_A.slice(0, -2)}${String(10 + i)}`,
        name: `Client ${String(i + 1)}`,
      }),
    );
    renderConsole(() => Promise.resolve(makePlatformStaffMe(clients)), ROUTES.home);
    await user.click(await screen.findByRole('button', { name: /Switch tenant/ }));
    const menu = screen.getByRole('menu');
    expect(within(menu).getAllByRole('menuitem')).toHaveLength(SWITCHER_SEARCH_THRESHOLD + 1);
    await user.type(screen.getByRole('textbox', { name: 'Search tenants' }), 'client 7');
    expect(
      within(menu)
        .getAllByRole('menuitem')
        .map((i) => i.textContent),
    ).toEqual(['Client 7MSM-2026-0007 · Full management']);
  });
});
