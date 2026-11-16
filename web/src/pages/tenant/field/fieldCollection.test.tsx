import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { cashService } from '../../../api/services/cashService';
import type { customerService } from '../../../api/services/customerService';
import { CUSTOMER, makePayment, page } from '../../../test/financeFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { FieldCollectionDialog } from './FieldCollectionDialog';

const mocks = vi.hoisted(() => ({
  getCustomer: vi.fn<typeof customerService.get>(),
  listCustomers: vi.fn<typeof customerService.list>(),
  recordCollection: vi.fn<typeof cashService.recordCollection>(),
}));
vi.mock('../../../api/services/customerService', () => ({
  customerService: { get: mocks.getCustomer, list: mocks.listCustomers },
}));
vi.mock('../../../api/services/cashService', () => ({
  cashService: { recordCollection: mocks.recordCollection },
}));

/** The seeded Supervisor role (no office oversight, no machine register). */
const SUPERVISOR = [
  'tenant.machine_report.submit',
  'tenant.meter.capture',
  'tenant.meter.read',
  'tenant.customer.read',
  'tenant.expense.read',
  'tenant.expense.write',
  'tenant.collection.record',
];

describe('FieldCollectionDialog', () => {
  it('records into the caller’s own custody', async () => {
    const user = userEvent.setup();
    mocks.listCustomers.mockResolvedValue(page([CUSTOMER]));
    mocks.recordCollection.mockResolvedValue(makePayment());
    const onRecorded = vi.fn();
    renderWithProviders(
      <FieldCollectionDialog timeZone="UTC" onClose={vi.fn()} onRecorded={onRecorded} />,
      { tenantPermissions: SUPERVISOR },
    );
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).queryByRole('combobox', { name: /^Job/ })).toBeNull();
    await user.click(within(dialog).getByRole('combobox', { name: /^Customer/ }));
    await user.click(await screen.findByRole('option', { name: 'ACME · Acme Builders' }));
    await user.type(within(dialog).getByRole('textbox', { name: /^Amount received/ }), '250000');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Next' }));
    expect(await within(dialog).findByText('Me (my custody)')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Record collection' }));
    await waitFor(() => {
      expect(mocks.recordCollection).toHaveBeenCalledWith(
        expect.objectContaining({
          customer_id: CUSTOMER.id,
          amount: '250000',
          staff_member_id: null,
        }),
        expect.any(String),
      );
    });
    expect(mocks.recordCollection.mock.calls[0]?.[0]).not.toHaveProperty('allocations');
    expect(onRecorded).toHaveBeenCalledTimes(1);
  });
});
