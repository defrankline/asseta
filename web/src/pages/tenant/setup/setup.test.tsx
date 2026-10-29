import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type {
  SetupChecklistDto,
  SetupStepDto,
  setupChecklistService,
} from '../../../api/services/setupChecklistService';
import { makeMe } from '../../../test/fixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { SetupBanner } from './SetupBanner';
import { SetupChecklistPage } from './SetupChecklistPage';

const m = vi.hoisted(() => ({
  get: vi.fn<typeof setupChecklistService.get>(),
  markNotNeeded: vi.fn<typeof setupChecklistService.markNotNeeded>(),
  undoNotNeeded: vi.fn<typeof setupChecklistService.undoNotNeeded>(),
  confirmControls: vi.fn<typeof setupChecklistService.confirmControls>(),
  dismiss: vi.fn<typeof setupChecklistService.dismiss>(),
  undismiss: vi.fn<typeof setupChecklistService.undismiss>(),
}));
vi.mock('../../../api/services/setupChecklistService', () => ({ setupChecklistService: m }));

const READ = [P.tenantSetupRead];
const MANAGE = [P.tenantSetupRead, P.tenantSetupManage, P.tenantMachineWrite];

function step(o: Partial<SetupStepDto> & Pick<SetupStepDto, 'key' | 'order' | 'title'>) {
  return {
    description: `${o.title} description`,
    status: 'TODO',
    done_count: null,
    total_count: null,
    link: '/tenant/machines',
    required_permission: 'tenant.machine.write',
    can_mark_not_needed: false,
    not_needed: null,
    checks: [],
    ...o,
  } satisfies SetupStepDto;
}

function checklist(o: Partial<SetupChecklistDto> = {}): SetupChecklistDto {
  return {
    steps: [
      step({
        key: 'COMPANY_SETTINGS',
        order: 1,
        title: 'Company settings',
        status: 'DONE',
        link: '/tenant/subscription',
      }),
      step({
        key: 'TRACKERS',
        order: 5,
        title: 'Trackers',
        done_count: 3,
        total_count: 5,
        can_mark_not_needed: true,
        link: '/tenant/machines?missing=tracker',
        checks: [
          {
            key: 'PRIMARY_TRACKER',
            label: 'Every active machine has a main tracker',
            done: false,
            optional: false,
            done_count: 3,
            total_count: 5,
            link: '/tenant/machines?missing=tracker',
            required_permission: 'tenant.tracker.write',
          },
          {
            key: 'ENROLLED',
            label: 'Every active machine is enrolled',
            done: true,
            optional: false,
            done_count: 5,
            total_count: 5,
            link: '/tenant/machines?missing=enrollment',
            required_permission: 'tenant.billing.enroll',
          },
        ],
      }),
      step({
        key: 'CONTROLS_CHOSEN',
        order: 8,
        title: 'Controls chosen',
        link: '/tenant/policies',
      }),
      step({
        key: 'METER_BASELINES',
        order: 11,
        title: 'Meter baselines',
        status: 'NOT_APPLICABLE',
      }),
      step({
        key: 'SITES',
        order: 6,
        title: 'Sites',
        status: 'NOT_NEEDED',
        can_mark_not_needed: true,
        not_needed: {
          reason: 'We work on customer yards',
          marked_by: 'u-1',
          marked_by_name: 'Owner One',
          marked_at: '2026-10-28T08:00:00Z',
        },
      }),
    ],
    steps_done: 2,
    steps_total: 4,
    percent: 50,
    complete: false,
    dismissed: false,
    as_of: '2026-10-29T08:00:00Z',
    ...o,
  };
}

beforeEach(() => {
  m.get.mockResolvedValue(checklist());
});

describe('go-live checklist page', () => {
  it('shows progress, numbered steps in order, counts, links and hides unused steps', async () => {
    renderWithProviders(<SetupChecklistPage />, { tenantPermissions: READ });
    expect(await screen.findByText('2 of 4 done')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: /2 of 4 done/ })).toHaveAttribute(
      'aria-valuenow',
      '50',
    );
    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(['Company settings', 'Trackers', 'Sites', 'Controls chosen']);
    expect(screen.queryByRole('heading', { name: 'Meter baselines' })).not.toBeInTheDocument();
    expect(
      screen.getByText(/Not used by your company, so left out: Meter baselines/),
    ).toBeVisible();

    const trackers = screen.getByRole('region', { name: 'Trackers' });
    // The step's count and its unfinished part's count.
    expect(within(trackers).getAllByText('3 of 5 machines')).toHaveLength(2);
    expect(within(trackers).getByText('To do')).toBeInTheDocument();
    expect(within(trackers).getByRole('link', { name: 'Go to Machines' })).toHaveAttribute(
      'href',
      '/tenant/machines?missing=tracker',
    );
    // Only the part still to do links on; the done part does not.
    expect(within(trackers).getByRole('link', { name: 'Open Machines' })).toHaveAttribute(
      'href',
      '/tenant/machines?missing=tracker',
    );
    expect(within(trackers).getAllByRole('link')).toHaveLength(2);

    const sites = screen.getByRole('region', { name: 'Sites' });
    expect(within(sites).getByText('Not needed')).toBeInTheDocument();
    expect(within(sites).getByText(/Owner One/)).toBeInTheDocument();
    expect(within(sites).getByText(/We work on customer yards/)).toBeInTheDocument();

    // Read-only holders see no owner choices.
    expect(screen.queryByRole('button', { name: 'Mark as not needed' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Undo' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Hide checklist banner' })).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Our default controls are fine' }),
    ).not.toBeInTheDocument();
  });

  it('marks a step as not needed with a reason and refreshes /me', async () => {
    const user = userEvent.setup();
    const reload = vi.fn();
    m.markNotNeeded.mockResolvedValue(checklist({ steps_done: 3 }));
    renderWithProviders(<SetupChecklistPage />, {
      tenantPermissions: MANAGE,
      session: { reload },
    });
    const trackers = await screen.findByRole('region', { name: 'Trackers' });
    await user.click(within(trackers).getByRole('button', { name: 'Mark as not needed' }));
    await user.type(screen.getByRole('textbox', { name: /Why it is not needed/ }), 'No trackers');
    await user.click(screen.getByRole('button', { name: 'Mark as not needed' }));
    await waitFor(() => {
      expect(m.markNotNeeded).toHaveBeenCalledTimes(1);
    });
    expect(m.markNotNeeded.mock.calls[0]?.slice(0, 2)).toEqual(['TRACKERS', 'No trackers']);
    expect(await screen.findByText('3 of 4 done')).toBeInTheDocument();
    expect(reload).toHaveBeenCalled();
  });

  it('undoes a not-needed mark', async () => {
    const user = userEvent.setup();
    m.undoNotNeeded.mockResolvedValue(checklist());
    renderWithProviders(<SetupChecklistPage />, { tenantPermissions: MANAGE });
    const sites = await screen.findByRole('region', { name: 'Sites' });
    await user.click(within(sites).getByRole('button', { name: 'Undo' }));
    await waitFor(() => {
      expect(m.undoNotNeeded).toHaveBeenCalledTimes(1);
    });
    expect(m.undoNotNeeded.mock.calls[0]?.[0]).toBe('SITES');
  });

  it('confirms the default controls with an optional note', async () => {
    const user = userEvent.setup();
    m.confirmControls.mockResolvedValue(checklist());
    renderWithProviders(<SetupChecklistPage />, { tenantPermissions: MANAGE });
    const controls = await screen.findByRole('region', { name: 'Controls chosen' });
    expect(within(controls).getByRole('link', { name: 'Go to Policies' })).toBeInTheDocument();
    await user.click(
      within(controls).getByRole('button', { name: 'Our default controls are fine' }),
    );
    await user.click(screen.getByRole('button', { name: 'Our default controls are fine' }));
    await waitFor(() => {
      expect(m.confirmControls).toHaveBeenCalledTimes(1);
    });
    expect(m.confirmControls.mock.calls[0]?.[0]).toBeNull();
  });

  it('hides the banner and offers to show it again', async () => {
    const user = userEvent.setup();
    m.dismiss.mockResolvedValue(checklist({ dismissed: true }));
    m.undismiss.mockResolvedValue(checklist({ dismissed: false }));
    renderWithProviders(<SetupChecklistPage />, { tenantPermissions: MANAGE });
    await user.click(await screen.findByRole('button', { name: 'Hide checklist banner' }));
    await user.click(await screen.findByRole('button', { name: 'Show banner again' }));
    await waitFor(() => {
      expect(m.undismiss).toHaveBeenCalledTimes(1);
    });
    expect(m.dismiss).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole('button', { name: 'Hide checklist banner' })).toBeVisible();
  });

  it('celebrates a complete checklist', async () => {
    m.get.mockResolvedValue(checklist({ complete: true, steps_done: 4, percent: 100 }));
    renderWithProviders(<SetupChecklistPage />, { tenantPermissions: READ });
    expect(await screen.findByText(/ready to go live/)).toBeInTheDocument();
  });
});

describe('go-live dashboard banner', () => {
  const tenant = makeMe().tenants[0];
  if (tenant === undefined) throw new Error('fixture tenant missing');
  const withSetup = (o: Partial<typeof tenant>) => ({
    ...tenant,
    setup_complete: false,
    setup_dismissed: false,
    setup_percent: 40,
    setup_steps_done: 4,
    setup_steps_total: 10,
    ...o,
  });

  it('shows progress from /me and links to the checklist', () => {
    renderWithProviders(<SetupBanner />, {
      tenantPermissions: READ,
      session: { activeTenant: withSetup({}) },
    });
    expect(screen.getByText('Get ready to go live — 4 of 10 done')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Continue setup' })).toHaveAttribute(
      'href',
      '/tenant/setup',
    );
  });

  it.each([
    ['complete', { setup_complete: true }, READ],
    ['dismissed', { setup_dismissed: true }, READ],
    ['without the read permission', {}, [P.tenantMachineRead]],
    ['when /me has no figures', { setup_complete: null }, READ],
  ])('stays hidden when %s', (_name, o, perms) => {
    renderWithProviders(<SetupBanner />, {
      tenantPermissions: perms,
      session: { activeTenant: withSetup(o) },
    });
    expect(screen.queryByText(/Get ready to go live/)).not.toBeInTheDocument();
  });
});
