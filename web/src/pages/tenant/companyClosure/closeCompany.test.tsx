import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { companyClosureService } from '../../../api/services/companyClosureService';
import { apiError, makeDeletionRequest } from '../../../test/closureFixtures';
import { TENANT_A } from '../../../test/fixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { DATA_PROTECTION_FIELDS } from '../policies/dataProtectionPolicyFields';
import { CloseCompanyPage } from './CloseCompanyPage';
import { nameMatches } from './closureDisplay';

const mocks = vi.hoisted(() => ({
  getStatus: vi.fn<typeof companyClosureService.getStatus>(),
  request: vi.fn<typeof companyClosureService.request>(),
  cancel: vi.fn<typeof companyClosureService.cancel>(),
}));
vi.mock('../../../api/services/companyClosureService', () => ({
  companyClosureService: {
    getStatus: mocks.getStatus,
    request: mocks.request,
    cancel: mocks.cancel,
  },
}));

const CLOSE = [P.tenantCompanyClose];
const status = (request: ReturnType<typeof makeDeletionRequest> | null) => ({
  tenant_id: TENANT_A,
  company_name: 'Acme Plant Hire',
  waiting_days: 30,
  request,
});

beforeEach(() => {
  mocks.getStatus.mockResolvedValue(status(null));
  mocks.request.mockResolvedValue(makeDeletionRequest());
  mocks.cancel.mockResolvedValue(makeDeletionRequest({ status: 'CANCELLED' }));
});
afterEach(() => {
  vi.clearAllMocks();
});

function renderPage(accessState: 'FULL' | 'READ_ONLY' = 'FULL', reload = vi.fn()) {
  renderWithProviders(<CloseCompanyPage />, {
    tenantPermissions: CLOSE,
    accessState,
    session: { reload },
  });
  return reload;
}

async function fillForm(name: string, reason = 'Selling the business') {
  await userEvent.type(await screen.findByLabelText(/Type the company name to confirm/), name);
  await userEvent.type(screen.getByLabelText(/^Reason/), reason);
}

describe('CloseCompanyPage without a request', () => {
  it('explains what happens and links to the data export', async () => {
    renderPage();
    expect(
      await screen.findByText(/All of Acme Plant Hire will be deleted 30 days after you confirm/),
    ).toBeInTheDocument();
    expect(screen.getByText(/The company becomes read-only immediately/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Data export' })).toHaveAttribute(
      'href',
      '/tenant/data-export',
    );
  });

  it('keeps Close company disabled until the name matches (any case)', async () => {
    renderPage();
    await fillForm('acme plant');
    const button = screen.getByRole('button', { name: 'Close company' });
    expect(button).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/Type the company name to confirm/), ' HIRE');
    expect(button).toBeEnabled();
  });

  it('asks a final confirmation, then requests and refreshes the session', async () => {
    const reload = renderPage();
    await fillForm('ACME PLANT HIRE');
    await userEvent.click(screen.getByRole('button', { name: 'Close company' }));
    expect(mocks.request).not.toHaveBeenCalled();
    const dialog = await screen.findByRole('dialog');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Close company' }));
    expect(mocks.request).toHaveBeenCalledWith(
      { confirm_name: 'ACME PLANT HIRE', reason: 'Selling the business' },
      expect.any(String),
    );
    expect(reload).toHaveBeenCalled();
  });

  it('shows a plain message when the server refuses', async () => {
    mocks.request.mockRejectedValue(apiError('MANDATE_NOT_ALLOWED', 'raw'));
    renderPage();
    await fillForm('Acme Plant Hire');
    await userEvent.click(screen.getByRole('button', { name: 'Close company' }));
    await userEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Close company' }),
    );
    expect(
      await screen.findByText(/Only the company's own owners can close it/),
    ).toBeInTheDocument();
  });

  it('matches names case-insensitively and ignores spaces', () => {
    expect(nameMatches('  acme ', 'ACME')).toBe(true);
    expect(nameMatches('', '')).toBe(false);
    expect(nameMatches('acm', 'acme')).toBe(false);
  });
});

describe('CloseCompanyPage with a request', () => {
  it('shows who asked, the deletion date with days left and cancels with a reason, even while read-only', async () => {
    mocks.getStatus.mockResolvedValue(status(makeDeletionRequest()));
    const reload = renderPage('READ_ONLY');
    expect(await screen.findByText('Closure requested')).toBeInTheDocument();
    expect(screen.getByText('Ops User')).toBeInTheDocument();
    expect(screen.getAllByText(/days left/).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole('button', { name: 'Cancel closure' }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.type(within(dialog).getByLabelText(/Reason/), 'Changed our mind');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel closure' }));
    expect(mocks.cancel).toHaveBeenCalledWith('Changed our mind', expect.any(String));
    expect(reload).toHaveBeenCalled();
  });

  it('shows a deletion in progress plainly, without cancel', async () => {
    mocks.getStatus.mockResolvedValue(status(makeDeletionRequest({ status: 'IN_PROGRESS' })));
    renderPage('READ_ONLY');
    expect(await screen.findByText(/can no longer be cancelled/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancel closure' })).not.toBeInTheDocument();
  });

  it('shows a completed deletion plainly', async () => {
    mocks.getStatus.mockResolvedValue(
      status(makeDeletionRequest({ status: 'COMPLETED', completed_at: '2026-12-01T08:00:00Z' })),
    );
    renderPage('READ_ONLY');
    expect(await screen.findByText(/data was deleted on/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Close company|Cancel closure/ })).toBeNull();
  });

  it('offers a new request after a cancelled one', async () => {
    mocks.getStatus.mockResolvedValue(
      status(makeDeletionRequest({ status: 'CANCELLED', cancelled_by_name: 'Owner Two' })),
    );
    renderPage();
    expect(await screen.findByText(/cancelled by Owner Two/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close company' })).toBeDisabled();
  });
});

describe('company deletion waiting period', () => {
  it('is platform-only: the tenant data protection form does not offer it', () => {
    expect(DATA_PROTECTION_FIELDS.map((f) => f.key)).not.toContain('company_deletion_waiting_days');
  });
});
