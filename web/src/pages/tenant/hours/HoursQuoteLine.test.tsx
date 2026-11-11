import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { HoursQuoteDto } from '../../../api/hoursTypes';
import type { hoursService } from '../../../api/services/hoursService';
import { HoursQuoteLine } from './HoursQuoteLine';
import { NO_RATE_QUOTE_TEXT, QUOTE_DEBOUNCE_MS } from './hoursQuote';

const mocks = vi.hoisted(() => ({
  quote: vi.fn<typeof hoursService.quotePurchase>(),
}));
vi.mock('../../../api/services/hoursService', () => ({
  hoursService: { quotePurchase: mocks.quote },
}));

const M = '11111111-1111-1111-1111-111111111111';
const C = '22222222-2222-2222-2222-222222222222';

function quote(over: Partial<HoursQuoteDto> = {}): HoursQuoteDto {
  return {
    machine_id: M,
    customer_id: null,
    hours: '6',
    hourly_rate: '95000.0000',
    discount_percent: '0',
    effective_rate: '95000.0000',
    amount: '570000.0000',
    currency: 'TZS',
    minimum_hours: '1',
    ...over,
  };
}

async function settle() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(QUOTE_DEBOUNCE_MS + 10);
  });
}

describe('HoursQuoteLine', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mocks.quote.mockReset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows the total once a machine and hours are set', async () => {
    mocks.quote.mockResolvedValue(quote());
    render(<HoursQuoteLine machineId={M} hours="6" customerId="" />);
    await settle();
    expect(screen.getByText('Total: TZS 570,000 (6 h × 95,000/h)')).toBeInTheDocument();
    expect(mocks.quote).toHaveBeenCalledWith(
      { machine_id: M, hours: '6', customer_id: undefined },
      expect.any(AbortSignal),
    );
  });

  it('words the customer discount', async () => {
    mocks.quote.mockResolvedValue(
      quote({ customer_id: C, discount_percent: '10.00', amount: '513000.0000' }),
    );
    render(<HoursQuoteLine machineId={M} hours="6" customerId={C} />);
    await settle();
    expect(
      screen.getByText('Total: TZS 513,000 (6 h × 95,000/h, less 10% discount)'),
    ).toBeInTheDocument();
    expect(mocks.quote.mock.calls[0]?.[0].customer_id).toBe(C);
  });

  it('explains a missing rate and shows other errors plainly', async () => {
    mocks.quote.mockRejectedValue(
      new ApiError({ status: 400, code: 'NO_RATE', message: 'x', correlationId: null }),
    );
    const { rerender } = render(<HoursQuoteLine machineId={M} hours="6" customerId="" />);
    await settle();
    expect(screen.getByText(NO_RATE_QUOTE_TEXT)).toBeInTheDocument();
    mocks.quote.mockRejectedValue(new Error('Network down'));
    rerender(<HoursQuoteLine machineId={M} hours="7" customerId="" />);
    await settle();
    expect(screen.getByText(/Network down/)).toBeInTheDocument();
  });

  it('debounces typing and refetches when the inputs change', async () => {
    mocks.quote.mockResolvedValue(quote());
    const { rerender } = render(<HoursQuoteLine machineId="" hours="6" customerId="" />);
    await settle();
    expect(mocks.quote).not.toHaveBeenCalled();
    rerender(<HoursQuoteLine machineId={M} hours="1" customerId="" />);
    rerender(<HoursQuoteLine machineId={M} hours="12" customerId="" />);
    await settle();
    expect(mocks.quote).toHaveBeenCalledTimes(1);
    expect(mocks.quote.mock.calls[0]?.[0].hours).toBe('12');
    rerender(<HoursQuoteLine machineId={M} hours="12" customerId={C} />);
    await settle();
    expect(mocks.quote).toHaveBeenCalledTimes(2);
  });
});
