import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { platformPaymentService } from '../../../api/services/platformPaymentService';
import type { RecordPaymentIn } from '../../../api/types';
import { INVOICE_ID, makeInvoice, makePayment } from '../../../test/billingFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { todayIsoDate } from '../../../utils/dates';
import { RecordPaymentDialog } from './RecordPaymentDialog';

const mocks = vi.hoisted(() => ({
  record: vi.fn<typeof platformPaymentService.record>(),
}));
const record = mocks.record;
vi.mock('../../../api/services/platformPaymentService', () => ({
  platformPaymentService: { record: mocks.record },
}));

describe('RecordPaymentDialog', () => {
  it('sends the contract payload in the invoice currency and reuses the key on retry', async () => {
    const user = userEvent.setup();
    record
      .mockRejectedValueOnce(
        new ApiError({
          status: null,
          code: 'network_error',
          message: 'Network error.',
          correlationId: null,
        }),
      )
      .mockResolvedValueOnce(makePayment());
    const onRecorded = vi.fn();
    renderWithProviders(
      <RecordPaymentDialog invoice={makeInvoice()} onClose={vi.fn()} onRecorded={onRecorded} />,
    );

    await user.type(screen.getByRole('textbox', { name: /^Reference/ }), 'CRDB-001');
    const amount = screen.getByRole('textbox', { name: /^Amount \(TZS\)/ });
    await user.type(amount, '400000');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(
      await screen.findByText('Amount cannot exceed the outstanding balance'),
    ).toBeInTheDocument();
    await user.clear(amount);
    await user.type(amount, '100000.50');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('TZS 100,000.50')).toBeInTheDocument();

    const submit = screen.getByRole('button', { name: 'Record payment' });
    await user.click(submit);
    expect(await screen.findByText('Network error.')).toBeInTheDocument();
    await user.click(submit);
    await waitFor(() => {
      expect(record).toHaveBeenCalledTimes(2);
    });

    const expected: RecordPaymentIn = {
      invoice_id: INVOICE_ID,
      amount: '100000.50',
      currency: 'TZS',
      method: 'BANK_TRANSFER',
      reference: 'CRDB-001',
      received_on: todayIsoDate(),
    };
    const [first, second] = record.mock.calls;
    expect(first?.[0]).toEqual(expected);
    expect(second?.[0]).toEqual(expected);
    expect(first?.[1]).toMatch(/^[0-9a-f-]{36}$/);
    expect(second?.[1]).toBe(first?.[1]);
    expect(onRecorded).toHaveBeenCalledTimes(1);
  });

  it('uses a fresh key when a new dialog is opened', async () => {
    const user = userEvent.setup();
    record.mockResolvedValue(makePayment());
    const submitOnce = async () => {
      const { unmount } = renderWithProviders(
        <RecordPaymentDialog invoice={makeInvoice()} onClose={vi.fn()} onRecorded={vi.fn()} />,
      );
      await user.type(screen.getByRole('textbox', { name: /^Reference/ }), 'REF-9');
      await user.type(screen.getByRole('textbox', { name: /^Amount/ }), '10');
      await user.click(screen.getByRole('button', { name: 'Next' }));
      await user.click(await screen.findByRole('button', { name: 'Record payment' }));
      await waitFor(() => {
        expect(record).toHaveBeenCalled();
      });
      unmount();
    };
    await submitOnce();
    await submitOnce();
    expect(record).toHaveBeenCalledTimes(2);
    expect(record.mock.calls[0]?.[1]).not.toBe(record.mock.calls[1]?.[1]);
  });
});
