import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { mandateService } from '../../../api/services/mandateService';
import { MANDATE_ID, makeMandateDetail, STAFF_ID } from '../../../test/mandateFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { MandateDetailDialog } from './MandateDetailDialog';

const mocks = vi.hoisted(() => ({
  get: vi.fn<typeof mandateService.get>(),
  listStaff: vi.fn<typeof mandateService.listStaff>(),
  listRoles: vi.fn<typeof mandateService.listRoles>(),
  assign: vi.fn<typeof mandateService.assign>(),
  removeAssignment: vi.fn<typeof mandateService.removeAssignment>(),
  end: vi.fn<typeof mandateService.end>(),
}));
vi.mock('../../../api/services/mandateService', () => ({ mandateService: mocks }));

const MANAGE = ['platform.mandate.read', 'platform.mandate.manage'];

beforeEach(() => {
  mocks.get.mockResolvedValue(makeMandateDetail());
  mocks.listStaff.mockResolvedValue([
    { user_id: STAFF_ID, email: 'amina@asseta.test', display_name: 'Amina Staff' },
  ]);
  mocks.listRoles.mockResolvedValue([{ key: 'dispatcher', permissions: ['tenant.job.write'] }]);
});

function renderDialog(permissions = MANAGE) {
  const onChanged = vi.fn();
  renderWithProviders(
    <MandateDetailDialog mandateId={MANDATE_ID} onClose={vi.fn()} onChanged={onChanged} />,
    { permissions },
  );
  return { onChanged };
}

describe('MandateDetailDialog', () => {
  it('shows the terms and staff assignments', async () => {
    renderDialog();
    expect(await screen.findByText('LTR-889')).toBeInTheDocument();
    const table = screen.getByRole('table', { name: 'Staff with access' });
    expect(within(table).getByText('Amina Staff')).toBeInTheDocument();
    expect(within(table).getByRole('button', { name: 'Remove' })).toBeInTheDocument();
  });

  it('requires a reason before ending, then sends the version it was decided on', async () => {
    const user = userEvent.setup();
    mocks.end.mockResolvedValue(makeMandateDetail({ status: 'ENDED', version: 4 }));
    const { onChanged } = renderDialog();
    await user.click(await screen.findByRole('button', { name: 'End mandate' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    expect(mocks.end).not.toHaveBeenCalled();

    await user.type(screen.getByRole('textbox', { name: /Reason for ending/ }), 'Contract over');
    await user.click(screen.getByRole('button', { name: 'End mandate' }));
    await waitFor(() => {
      expect(mocks.end).toHaveBeenCalledWith(
        MANDATE_ID,
        { version: 3, reason: 'Contract over' },
        expect.any(String),
      );
    });
    expect(onChanged).toHaveBeenCalled();
    // Ended: no further staffing or end controls.
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'End mandate' })).not.toBeInTheDocument();
    });
  });

  it('shows the server message when ending fails (e.g. a stale version)', async () => {
    const user = userEvent.setup();
    mocks.end.mockRejectedValue(
      new ApiError({
        status: 409,
        code: 'STALE_VERSION',
        message: 'The mandate changed; reload and try again',
        correlationId: 'corr-1',
      }),
    );
    renderDialog();
    await user.type(await screen.findByRole('textbox', { name: /Reason for ending/ }), 'Done');
    await user.click(screen.getByRole('button', { name: 'End mandate' }));
    expect(
      await screen.findByText('The mandate changed; reload and try again (ref corr-1)'),
    ).toBeInTheDocument();
  });

  it('assigns platform staff to a client role', async () => {
    const user = userEvent.setup();
    mocks.assign.mockResolvedValue(makeMandateDetail());
    renderDialog();
    await user.click(await screen.findByRole('combobox', { name: /Platform staff/ }));
    await user.click(await screen.findByRole('option', { name: /Amina Staff/ }));
    await user.click(screen.getByRole('combobox', { name: /Client role/ }));
    await user.click(await screen.findByRole('option', { name: 'dispatcher' }));
    await user.click(screen.getByRole('button', { name: 'Assign' }));
    await waitFor(() => {
      expect(mocks.assign).toHaveBeenCalledWith(
        MANDATE_ID,
        { user_id: STAFF_ID, role_key: 'dispatcher' },
        expect.any(String),
      );
    });
  });

  it('is read-only without platform.mandate.manage', async () => {
    renderDialog(['platform.mandate.read']);
    expect(await screen.findByText('LTR-889')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'End mandate' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Assign' })).not.toBeInTheDocument();
  });
});
