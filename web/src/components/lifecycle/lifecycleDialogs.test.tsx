import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/ApiError';
import { renderWithProviders } from '../../test/renderWithProviders';
import { DeactivateDialog, ReactivateDialog } from './DeactivateDialog';
import { LifecycleActionDialog, STALE_RECORD_MESSAGE } from './LifecycleActionDialog';

const apiError = (code: string, message: string) =>
  new ApiError({ status: 409, code, message, correlationId: 'corr-1' });

function renderDeactivate(onConfirm: (reason: string, key: string) => Promise<string>) {
  const handlers = { onDone: vi.fn(), onClose: vi.fn(), onReload: vi.fn() };
  renderWithProviders(
    <DeactivateDialog<string>
      entityLabel="EX-01 · Excavator"
      noun="machine"
      onConfirm={onConfirm}
      errorHints={{ MACHINE_HAS_OPEN_JOB: 'Complete or cancel the open job first.' }}
      {...handlers}
    />,
  );
  return handlers;
}

describe('DeactivateDialog', () => {
  it('explains that nothing is deleted and requires a reason', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn<(reason: string, key: string) => Promise<string>>();
    renderDeactivate(onConfirm);
    expect(screen.getByText(/stays in the system with all of its history/)).toBeInTheDocument();
    expect(screen.getByText(/Nothing is deleted/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), '   ');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('calls the service with the trimmed reason and an idempotency key', async () => {
    const user = userEvent.setup();
    const onConfirm = vi
      .fn<(reason: string, key: string) => Promise<string>>()
      .mockResolvedValue('saved');
    const { onDone, onClose } = renderDeactivate(onConfirm);
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), '  Sold at auction ');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    await waitFor(() => {
      expect(onDone).toHaveBeenCalledWith('saved');
    });
    const [reason, key] = onConfirm.mock.calls[0] ?? [];
    expect(reason).toBe('Sold at auction');
    expect(typeof key).toBe('string');
    expect(onClose).toHaveBeenCalled();
  });

  it('keeps the dialog open and shows a server business error with its code and hint', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn(() =>
      Promise.reject(apiError('MACHINE_HAS_OPEN_JOB', 'The machine has an open job.')),
    );
    const { onDone, onClose } = renderDeactivate(onConfirm);
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Sold');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(
      await screen.findByText(
        'MACHINE_HAS_OPEN_JOB: The machine has an open job. — Complete or cancel the open job first. (ref corr-1)',
      ),
    ).toBeInTheDocument();
    expect(onDone).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.queryByText(STALE_RECORD_MESSAGE)).not.toBeInTheDocument();
  });

  it('offers Reload on STALE_VERSION', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn(() => Promise.reject(apiError('STALE_VERSION', 'Modified')));
    const { onReload, onClose } = renderDeactivate(onConfirm);
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Sold');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(await screen.findByText(STALE_RECORD_MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reload' }));
    expect(onReload).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalled();
  });
});

describe('ReactivateDialog', () => {
  it('reactivates with the given reason', async () => {
    const user = userEvent.setup();
    const onConfirm = vi
      .fn<(reason: string, key: string) => Promise<number>>()
      .mockResolvedValue(1);
    const onDone = vi.fn();
    renderWithProviders(
      <ReactivateDialog<number>
        entityLabel="C-01 · Acme"
        noun="customer"
        onConfirm={onConfirm}
        onDone={onDone}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText(/will be active again/)).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Won back');
    await user.click(screen.getByRole('button', { name: 'Reactivate' }));
    await waitFor(() => {
      expect(onDone).toHaveBeenCalledWith(1);
    });
    expect(onConfirm.mock.calls[0]?.[0]).toBe('Won back');
  });
});

describe('LifecycleActionDialog', () => {
  it('is a plain confirmation when the endpoint takes no reason', async () => {
    const user = userEvent.setup();
    const onConfirm = vi
      .fn<(reason: string, key: string) => Promise<boolean>>()
      .mockResolvedValue(true);
    renderWithProviders(
      <LifecycleActionDialog<boolean>
        title="Return to service"
        description="Back to work."
        confirmLabel="Return to service"
        reason="none"
        onConfirm={onConfirm}
        onDone={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Return to service' }));
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledTimes(1);
    });
    expect(onConfirm.mock.calls[0]?.[0]).toBe('');
  });

  it('accepts an empty optional reason', async () => {
    const user = userEvent.setup();
    const onConfirm = vi
      .fn<(reason: string, key: string) => Promise<boolean>>()
      .mockResolvedValue(true);
    renderWithProviders(
      <LifecycleActionDialog<boolean>
        title="Suspend"
        description="Pause."
        confirmLabel="Suspend"
        reason="optional"
        onConfirm={onConfirm}
        onDone={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByRole('textbox', { name: 'Reason (optional)' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Suspend' }));
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledTimes(1);
    });
  });
});
