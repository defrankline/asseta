// eslint-disable-next-line no-restricted-imports -- the test drives the real HTTP client end to end
import { AxiosError, AxiosHeaders, type AxiosAdapter } from 'axios';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { createApiClient, createHttpClient } from '../api/client';
import { registerRequestContext, requestContext } from '../api/requestContext';
import type { MeResponse } from '../api/types';
import { NotificationProvider } from '../notifications/NotificationProvider';
import { SessionProvider } from '../session/SessionProvider';
import { storeMode } from '../session/modeStorage';
import { useSession } from '../session/useSession';
import { TENANT_A, TENANT_B } from '../test/fixtures';
import { makePlatformStaffMe, mandatedTenant } from '../test/mandateFixtures';
import { MandateBanner } from './MandateBanner';
import { TenantSwitcher } from './TenantSwitcher';

function ModeProbe() {
  const { mode } = useSession();
  return <span data-testid="mode">{mode.kind === 'tenant' ? mode.tenantId : mode.kind}</span>;
}

function renderShell(loadMe: (signal: AbortSignal) => Promise<MeResponse>, onLost = vi.fn()) {
  return render(
    <NotificationProvider>
      <MemoryRouter>
        <SessionProvider loadMe={loadMe} onMandateLost={onLost}>
          <TenantSwitcher />
          <MandateBanner />
          <ModeProbe />
        </SessionProvider>
      </MemoryRouter>
    </NotificationProvider>,
  );
}

const twoClients = () =>
  makePlatformStaffMe([
    mandatedTenant(),
    mandatedTenant({
      tenant_id: TENANT_A,
      name: 'Pwani Plant Hire',
      mandate: {
        mandate_id: TENANT_A,
        reference: 'MSM-2026-0009',
        scope: 'OPERATIONS',
        ends_on: null,
      },
    }),
  ]);

let restore: (() => void) | null = null;
beforeEach(() => {
  window.localStorage.clear();
});
afterEach(() => {
  restore?.();
  restore = null;
});

describe('Switch tenant menu', () => {
  it('lists "Asseta platform" first, then each mandated client with its reference and scope', async () => {
    const user = userEvent.setup();
    renderShell(() => Promise.resolve(twoClients()));
    // Platform staff start in their own context; a mandated client is never entered implicitly.
    expect(await screen.findByTestId('mode')).toHaveTextContent('platform');
    await user.click(screen.getByRole('button', { name: /Switch tenant/ }));
    const items = within(screen.getByRole('menu')).getAllByRole('menuitem');
    expect(items.map((i) => i.textContent)).toEqual([
      'Asseta platformPlatform console',
      'Kilimo HaulageMSM-2026-0007 · Full management',
      'Pwani Plant HireMSM-2026-0009 · Operations only',
    ]);
  });

  it('forces a token refresh before switching into a mandated client', async () => {
    const user = userEvent.setup();
    let finishRefresh: () => void = () => undefined;
    const refresh = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finishRefresh = resolve;
        }),
    );
    restore = registerRequestContext({ refreshAccessToken: refresh });
    renderShell(() => Promise.resolve(makePlatformStaffMe()));
    expect(await screen.findByTestId('mode')).toHaveTextContent('platform');

    await user.click(screen.getByRole('button', { name: /Switch tenant/ }));
    await user.click(screen.getByRole('menuitem', { name: /Kilimo Haulage/ }));
    expect(refresh).toHaveBeenCalledTimes(1);
    // Still in the platform context until the refreshed token (with the mandate group) arrives.
    expect(screen.getByTestId('mode')).toHaveTextContent('platform');

    finishRefresh();
    await waitFor(() => {
      expect(screen.getByTestId('mode')).toHaveTextContent(TENANT_B);
    });
  });

  it('stays in the platform context when the forced refresh fails', async () => {
    const user = userEvent.setup();
    restore = registerRequestContext({
      refreshAccessToken: () => Promise.reject(new Error('Session expired')),
    });
    renderShell(() => Promise.resolve(makePlatformStaffMe()));
    await user.click(await screen.findByRole('button', { name: /Switch tenant/ }));
    await user.click(screen.getByRole('menuitem', { name: /Kilimo Haulage/ }));
    expect(await screen.findByText('Session expired')).toBeInTheDocument();
    expect(screen.getByTestId('mode')).toHaveTextContent('platform');
  });
});

describe('Mandate banner', () => {
  it('shows while acting under a mandate and "Return to Asseta platform" switches back', async () => {
    const user = userEvent.setup();
    storeMode({ kind: 'tenant', tenantId: TENANT_B });
    renderShell(() => Promise.resolve(makePlatformStaffMe()));
    expect(await screen.findByTestId('mode')).toHaveTextContent(TENANT_B);
    const banner = screen.getByRole('status');
    expect(banner).toHaveTextContent(
      'Acting for Kilimo Haulage under managed-service mandate MSM-2026-0007 (Full management). Everything you do is recorded for the client.',
    );

    await user.click(screen.getByRole('button', { name: 'Return to Asseta platform' }));
    await waitFor(() => {
      expect(screen.getByTestId('mode')).toHaveTextContent('platform');
    });
    expect(screen.queryByText(/Acting for/)).not.toBeInTheDocument();
  });

  it('is not shown for ordinary tenant members', async () => {
    storeMode({ kind: 'tenant', tenantId: TENANT_B });
    renderShell(() => Promise.resolve(makePlatformStaffMe([mandatedTenant({ mandate: null })])));
    expect(await screen.findByText(TENANT_B)).toBeInTheDocument();
    expect(screen.queryByText(/Acting for/)).not.toBeInTheDocument();
  });
});

describe('Mandate no longer in force', () => {
  const mandateEnded: AxiosAdapter = (config) =>
    Promise.reject(
      new AxiosError('fail', 'ERR_BAD_REQUEST', config, null, {
        data: {
          error: {
            code: 'MANDATE_ENDED',
            message: 'The managed-service mandate for this tenant is not in force',
            correlation_id: 'corr-9',
            details: [],
          },
        },
        status: 403,
        statusText: 'Forbidden',
        headers: new AxiosHeaders(),
        config,
      }),
    );

  it('returns to the platform context, reloads /me and notifies on MANDATE_ENDED', async () => {
    storeMode({ kind: 'tenant', tenantId: TENANT_B });
    const loadMe = vi
      .fn<(signal: AbortSignal) => Promise<MeResponse>>()
      .mockResolvedValueOnce(makePlatformStaffMe())
      .mockResolvedValue(makePlatformStaffMe([]));
    const onLost = vi.fn();
    renderShell(loadMe, onLost);
    expect(await screen.findByTestId('mode')).toHaveTextContent(TENANT_B);

    await waitFor(() => {
      expect(requestContext.getActiveTenantId()).toBe(TENANT_B);
    });
    // Any tenant-scoped call through the real HTTP client and request context.
    const instance = createHttpClient('/api/v1', requestContext);
    instance.defaults.adapter = mandateEnded;
    const api = createApiClient(instance);
    await expect(api.get('/tenant/machines', { tenantScoped: true })).rejects.toMatchObject({
      code: 'MANDATE_ENDED',
    });
    // A second refused call in flight must not notify twice.
    await expect(api.get('/tenant/jobs', { tenantScoped: true })).rejects.toMatchObject({
      code: 'MANDATE_ENDED',
    });

    expect(
      await screen.findByText(
        'The managed-service mandate for Kilimo Haulage is no longer in force.',
      ),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId('mode')).toHaveTextContent('platform');
    });
    expect(loadMe).toHaveBeenCalledTimes(2);
    expect(onLost).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/Acting for/)).not.toBeInTheDocument();
  });
});
