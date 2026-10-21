import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/ApiError';
import type { LifecycleReasonIn } from '../../api/lifecycle';
import { renderWithProviders } from '../../test/renderWithProviders';
import { StaleVersionAlert } from './StaleVersionAlert';
import { useLifecycleDialog, type LifecycleKind } from './useLifecycleDialog';
import { useStaleVersion } from './useStaleVersion';

interface Rec {
  id: string;
  name: string;
  version: number;
}
const REC: Rec = { id: 'r1', name: 'Acme', version: 4 };

type Call = (record: Rec, body: LifecycleReasonIn, key: string) => Promise<Rec>;

function Harness(props: { deactivate: Call; reactivate: Call; onDone: () => void }) {
  const { open, dialog } = useLifecycleDialog<Rec>({
    labelOf: (r) => r.name,
    noun: 'customer',
    deactivate: props.deactivate,
    reactivate: props.reactivate,
    onDone: props.onDone,
    onReload: vi.fn(),
    deactivateLabel: 'Close',
  });
  const btn = (kind: LifecycleKind) => (
    <button
      type="button"
      onClick={() => {
        open(kind, REC);
      }}
    >
      open {kind}
    </button>
  );
  return (
    <>
      {btn('deactivate')}
      {btn('reactivate')}
      {dialog}
    </>
  );
}

describe('useLifecycleDialog', () => {
  it('deactivates with the reason using the domain label, then reports the saved record', async () => {
    const user = userEvent.setup();
    const deactivate = vi.fn<Call>().mockResolvedValue({ ...REC, version: 5 });
    const onDone = vi.fn();
    renderWithProviders(<Harness deactivate={deactivate} reactivate={vi.fn()} onDone={onDone} />);
    await user.click(screen.getByRole('button', { name: 'open deactivate' }));
    expect(screen.getByRole('dialog', { name: 'Close Acme' })).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'ab');
    await user.click(screen.getByRole('button', { name: 'Close' }));
    expect(await screen.findByText('At least 3 characters')).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'c');
    await user.click(screen.getByRole('button', { name: 'Close' }));
    await waitFor(() => {
      expect(onDone).toHaveBeenCalledWith({ ...REC, version: 5 }, 'deactivate');
    });
    expect(deactivate.mock.calls[0]?.[1]).toEqual({ reason: 'abc' });
  });

  it('reactivates', async () => {
    const user = userEvent.setup();
    const reactivate = vi.fn<Call>().mockResolvedValue(REC);
    const onDone = vi.fn();
    renderWithProviders(<Harness deactivate={vi.fn()} reactivate={reactivate} onDone={onDone} />);
    await user.click(screen.getByRole('button', { name: 'open reactivate' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Won back');
    await user.click(screen.getByRole('button', { name: 'Reactivate' }));
    await waitFor(() => {
      expect(onDone).toHaveBeenCalledWith(REC, 'reactivate');
    });
  });
});

function StaleHarness({ call, onReload }: { call: () => Promise<void>; onReload: () => void }) {
  const { stale, guard } = useStaleVersion();
  return (
    <>
      {stale && <StaleVersionAlert onReload={onReload} />}
      <button
        type="button"
        onClick={() => {
          guard(call).catch(() => undefined);
        }}
      >
        save
      </button>
    </>
  );
}

describe('useStaleVersion + StaleVersionAlert', () => {
  it('shows Reload only after STALE_VERSION', async () => {
    const user = userEvent.setup();
    const onReload = vi.fn();
    const call = vi
      .fn<() => Promise<void>>()
      .mockRejectedValueOnce(
        new ApiError({ status: 422, code: 'NO_RATE', message: 'x', correlationId: null }),
      )
      .mockRejectedValueOnce(
        new ApiError({ status: 409, code: 'STALE_VERSION', message: 'x', correlationId: null }),
      );
    renderWithProviders(<StaleHarness call={call} onReload={onReload} />);
    await user.click(screen.getByRole('button', { name: 'save' }));
    expect(screen.queryByRole('button', { name: 'Reload' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'save' }));
    await user.click(await screen.findByRole('button', { name: 'Reload' }));
    expect(onReload).toHaveBeenCalledTimes(1);
  });
});
