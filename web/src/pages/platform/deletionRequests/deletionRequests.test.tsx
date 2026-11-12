import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { companyClosureService } from '../../../api/services/companyClosureService';
import { apiError, makeDeletionRequest, REQUEST_ID } from '../../../test/closureFixtures';
import { page } from '../../../test/financeFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { DeletionRequestDetailPage, RUN_NOW_WARNING } from './DeletionRequestDetailPage';
import { DeletionRequestsPage } from './DeletionRequestsPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof companyClosureService.list>(),
  get: vi.fn<typeof companyClosureService.get>(),
  executeNow: vi.fn<typeof companyClosureService.executeNow>(),
}));
vi.mock('../../../api/services/companyClosureService', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../../api/services/companyClosureService')>();
  return {
    ...actual,
    companyClosureService: { list: mocks.list, get: mocks.get, executeNow: mocks.executeNow },
  };
});

const READ = [P.platformTenantDeletionRead];
const EXECUTE = [P.platformTenantDeletionRead, P.platformTenantDeletionExecute];
const DETAIL = `/platform/deletion-requests/${REQUEST_ID}`;

beforeEach(() => {
  mocks.list.mockResolvedValue(page([makeDeletionRequest()]));
  mocks.get.mockResolvedValue(
    makeDeletionRequest({
      status: 'IN_PROGRESS',
      attempts: 2,
      steps_done: ['snapshot', 'subscription'],
      last_error: 'object store unavailable',
    }),
  );
  mocks.executeNow.mockResolvedValue(makeDeletionRequest());
});
afterEach(() => {
  vi.clearAllMocks();
});

function renderRoutes(permissions: string[], route: string) {
  renderWithProviders(
    <Routes>
      <Route path="/platform/deletion-requests" element={<DeletionRequestsPage />} />
      <Route
        path="/platform/deletion-requests/:requestId"
        element={<DeletionRequestDetailPage />}
      />
    </Routes>,
    { permissions, route },
  );
}

describe('DeletionRequestsPage', () => {
  it('lists requests, filters by status and opens one', async () => {
    renderRoutes(READ, '/platform/deletion-requests');
    expect(await screen.findByText('Tenant A')).toBeInTheDocument();
    expect(screen.getByText('Closure requested')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('combobox', { name: 'Status' }));
    await userEvent.click(await screen.findByRole('option', { name: 'Deletion in progress' }));
    await waitFor(() => {
      expect(mocks.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ filters: { status: 'IN_PROGRESS' } }),
        expect.anything(),
      );
    });

    await userEvent.click(screen.getByText('Tenant A'));
    expect(await screen.findByText('Steps done')).toBeInTheDocument();
  });
});

describe('DeletionRequestDetailPage', () => {
  it('shows steps done, attempts and the last error', async () => {
    renderRoutes(READ, DETAIL);
    expect(await screen.findByText('object store unavailable')).toBeInTheDocument();
    const steps = screen.getByRole('list', { name: 'Deletion steps' });
    expect(within(steps).getAllByText('Done')).toHaveLength(2);
    expect(within(steps).getAllByText('Not yet')).toHaveLength(4);
    expect(screen.getByText('Attempts').nextSibling).toHaveTextContent('2');
    expect(screen.queryByRole('button', { name: 'Run now' })).not.toBeInTheDocument();
  });

  it('runs now with a reason after the written-request warning', async () => {
    renderRoutes(EXECUTE, DETAIL);
    await userEvent.click(await screen.findByRole('button', { name: 'Run now' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(RUN_NOW_WARNING)).toBeInTheDocument();
    await userEvent.type(within(dialog).getByLabelText(/Reason/), 'Owner e-mail of 10 Nov');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Run now' }));
    expect(mocks.executeNow).toHaveBeenCalledWith(
      REQUEST_ID,
      'Owner e-mail of 10 Nov',
      expect.any(String),
    );
  });

  it('keeps a refusal in the dialog', async () => {
    mocks.executeNow.mockRejectedValue(
      apiError('DELETION_NOT_ACTIVE', 'This request is CANCELLED'),
    );
    renderRoutes(EXECUTE, DETAIL);
    await userEvent.click(await screen.findByRole('button', { name: 'Run now' }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.type(within(dialog).getByLabelText(/Reason/), 'Owner e-mail');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Run now' }));
    expect(
      await within(dialog).findByText(/DELETION_NOT_ACTIVE|cancelled or has already finished/),
    ).toBeInTheDocument();
  });

  it('offers no Run now on a finished request', async () => {
    mocks.get.mockResolvedValue(makeDeletionRequest({ status: 'COMPLETED' }));
    renderRoutes(EXECUTE, DETAIL);
    expect(await screen.findByText('Deleted')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Run now' })).not.toBeInTheDocument();
  });
});
