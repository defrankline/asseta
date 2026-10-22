import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { HomeRedirect } from '../pages/HomeRedirect';
import { beforeEach, describe, expect, it } from 'vitest';
import { SessionContext } from '../session/SessionContext';
import { makeMe, makeSession, TENANT_A } from '../test/fixtures';
import { makeGroupedTenantMe, TENANT_MENUS } from '../test/navFixtures';
import { SideNav } from './SideNav';

const STORAGE_KEY = 'asseta.nav.groups';

function renderNav(route: string, me = makeGroupedTenantMe()) {
  const session = makeSession(me, { kind: 'tenant', tenantId: TENANT_A });
  return render(
    <SessionContext.Provider value={session}>
      <MemoryRouter initialEntries={[route]}>
        <SideNav mobileOpen={false} onClose={() => undefined} />
      </MemoryRouter>
    </SessionContext.Provider>,
  );
}

function header(name: string) {
  const nav = screen.getByRole('navigation', { name: 'Main' });
  return within(nav).getByRole('button', { name });
}

describe('SideNav', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('renders group headers in order and expands only the active group on first visit', () => {
    renderNav('/tenant/customers');
    const nav = screen.getByRole('navigation', { name: 'Main' });
    expect(
      within(nav)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['Overview', 'Operations', 'Fleet', 'Finance', 'Administration']);
    expect(header('Operations')).toHaveAttribute('aria-expanded', 'true');
    expect(header('Fleet')).toHaveAttribute('aria-expanded', 'false');
    const ops = within(nav).getByRole('list', { name: 'Operations' });
    expect(header('Operations')).toHaveAttribute('aria-controls', ops.id);
    expect(
      within(ops)
        .getAllByRole('link')
        .map((l) => l.textContent),
    ).toEqual(['Jobs', 'Customers']);
    expect(within(ops).getByRole('link', { name: 'Customers' })).toHaveClass('active');
    expect(within(nav).queryByRole('link', { name: 'Machines' })).not.toBeInTheDocument();
  });

  it('hides groups without visible menus', () => {
    renderNav(
      '/tenant/finance',
      makeGroupedTenantMe(TENANT_MENUS.filter((m) => m.group === 'tenant.finance')),
    );
    const nav = screen.getByRole('navigation', { name: 'Main' });
    expect(
      within(nav)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['Finance', 'Administration']);
  });

  it('toggles a group from the keyboard and remembers the choice per viewer', async () => {
    const user = userEvent.setup();
    const { unmount } = renderNav('/tenant/fleet');
    header('Fleet').focus();
    await user.keyboard('{Enter}');
    expect(header('Fleet')).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('link', { name: 'Machines' })).toBeInTheDocument();
    header('Overview').focus();
    await user.keyboard(' ');
    expect(header('Overview')).toHaveAttribute('aria-expanded', 'false');
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '{}')).toEqual({
      'tenant.overview': false,
      'tenant.fleet': true,
    });

    unmount();
    renderNav('/tenant/policies');
    expect(header('Fleet')).toHaveAttribute('aria-expanded', 'true');
    expect(header('Administration')).toHaveAttribute('aria-expanded', 'true'); // active route
    expect(header('Finance')).toHaveAttribute('aria-expanded', 'false');
  });

  it('expands the group of the active route even if it was collapsed before', () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ 'tenant.finance': false }));
    renderNav('/tenant/finance/invoices/1');
    expect(header('Finance')).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('link', { name: 'Hire finance' })).toHaveClass('active');
  });

  it('works without storage', () => {
    window.localStorage.setItem(STORAGE_KEY, 'not json');
    renderNav('/tenant/jobs');
    expect(header('Operations')).toHaveAttribute('aria-expanded', 'true');
  });
});

describe('HomeRedirect', () => {
  function landOn(session: ReturnType<typeof makeSession>) {
    render(
      <SessionContext.Provider value={session}>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route path="/" element={<HomeRedirect />} />
            <Route path="/tenant/dashboard" element={<p>Tenant dashboard page</p>} />
            <Route path="/tenant/fleet" element={<p>Fleet map page</p>} />
            <Route path="/platform" element={<p>Dashboard page</p>} />
            <Route path="*" element={<p>Somewhere else</p>} />
          </Routes>
        </MemoryRouter>
      </SessionContext.Provider>,
    );
  }

  it('lands tenant users on the first Overview item: the Dashboard', () => {
    landOn(makeSession(makeGroupedTenantMe(), { kind: 'tenant', tenantId: TENANT_A }));
    expect(screen.getByText('Tenant dashboard page')).toBeInTheDocument();
  });

  it('lands on the Fleet map when the role has no Dashboard menu', () => {
    const menus = TENANT_MENUS.filter((m) => m.key !== 'tenant.dashboard');
    landOn(makeSession(makeGroupedTenantMe(menus), { kind: 'tenant', tenantId: TENANT_A }));
    expect(screen.getByText('Fleet map page')).toBeInTheDocument();
  });

  it('lands platform staff on the first Overview item: the Dashboard', () => {
    const me = makeMe({
      platform_permissions: ['platform.dashboard.read', 'platform.tenant.read'],
      platform_menus: [
        {
          key: 't',
          label: 'Tenants',
          path: '/platform/tenants',
          order: 20,
          group: 'platform.tenants',
        },
        { key: 'd', label: 'Dashboard', path: '/platform', order: 10, group: 'platform.overview' },
      ],
      platform_menu_groups: [
        { key: 'platform.tenants', label: 'Tenants', order: 20 },
        { key: 'platform.overview', label: 'Overview', order: 10 },
      ],
    });
    landOn(makeSession(me, { kind: 'platform' }));
    expect(screen.getByText('Dashboard page')).toBeInTheDocument();
  });
});
