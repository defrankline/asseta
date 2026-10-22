import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { platformInvoiceService } from '../../../api/services/platformInvoiceService';
import type { platformPaymentService } from '../../../api/services/platformPaymentService';
import type { TenantDto } from '../../../api/types';
import { makeInvoice, makePlatformPayment } from '../../../test/fakePlatformInvoicingService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { PaymentsPage } from './PaymentsPage';

const TENANT = { id: 'tenant-1', display_name: 'Kilimanjaro Plant Hire' } as TenantDto;

const pay = vi.hoisted(() => ({
  list: vi.fn<typeof platformPaymentService.list>(),
  record: vi.fn<typeof platformPaymentService.record>(),
  decide: vi.fn<typeof platformPaymentService.decide>(),
  allocate: vi.fn<typeof platformPaymentService.allocate>(),
}));
const inv = vi.hoisted(() => ({
  list: vi.fn<typeof platformInvoiceService.list>(),
  get: vi.fn<typeof platformInvoiceService.get>(),
}));
vi.mock('../../../api/services/platformPaymentService', () => ({ platformPaymentService: pay }));
vi.mock('../../../api/services/platformInvoiceService', () => ({ platformInvoiceService: inv }));
vi.mock('../shared/platformLookups', () => ({
  tenantId: (t: TenantDto) => t.id,
  tenantLabel: (t: TenantDto) => t.display_name,
  searchTenants: () => Promise.resolve([TENANT]),
  resolveTenant: () => Promise.resolve(TENANT),
}));

const MANAGE = [P.platformPaymentRead, P.platformPaymentManage];
const RELEASED = makePlatformPayment({
  id: 'pay-2',
  reference: 'BANK-77',
  invoice_id: null,
  unallocated: '120000.00',
  allocations: [],
});

beforeEach(() => {
  pay.list.mockResolvedValue({
    items: [makePlatformPayment(), RELEASED],
    total: 2,
    page: 1,
    page_size: 25,
  });
  inv.list.mockResolvedValue({ items: [makeInvoice()], total: 1, page: 1, page_size: 20 });
  inv.get.mockResolvedValue(makeInvoice());
});

describe('Platform payments', () => {
  it('shows tenant-level payments, allocations and unallocated money; Allocate needs manage', async () => {
    const view = renderWithProviders(<PaymentsPage />, { permissions: [P.platformPaymentRead] });
    expect(await screen.findByText('BANK-77')).toBeInTheDocument();
    expect(screen.getAllByText('Tenant-level')).toHaveLength(2);
    expect(screen.getByText('Unallocated TZS 120,000.00')).toBeInTheDocument();
    expect(screen.getByText(/1 allocation \(incl. specific lines\)/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Allocate' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Record payment' })).not.toBeInTheDocument();
    view.unmount();
    renderWithProviders(<PaymentsPage />, { permissions: MANAGE });
    expect(await screen.findByRole('button', { name: 'Allocate' })).toBeInTheDocument();
  });

  it('two-person rule: the recorder sees no Verify/Reject, another staff member does', async () => {
    const me = '33333333-3333-4333-8333-333333333333';
    pay.list.mockResolvedValue({
      items: [
        makePlatformPayment({ id: 'own', reference: 'OWN-1', status: 'RECORDED', recorded_by: me }),
        makePlatformPayment({
          id: 'other',
          reference: 'OTHER-1',
          status: 'RECORDED',
          recorded_by: 'someone-else',
        }),
      ],
      total: 2,
      page: 1,
      page_size: 25,
    });
    renderWithProviders(<PaymentsPage />, { permissions: MANAGE });
    expect(
      await screen.findByText('Recorded by you — another staff member must verify'),
    ).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Verify' })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: 'Reject' })).toHaveLength(1);
  });

  it('filters by tenant on the server', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaymentsPage />, { permissions: MANAGE });
    await screen.findByText('BANK-77');
    await user.click(screen.getByRole('combobox', { name: 'Tenant' }));
    await user.click(await screen.findByRole('option', { name: 'Kilimanjaro Plant Hire' }));
    await waitFor(() => {
      expect(pay.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ tenant_id: 'tenant-1' }),
        expect.any(AbortSignal),
      );
    });
  });

  it('records a tenant-level payment (no invoice) with tenant_id', async () => {
    const user = userEvent.setup();
    pay.record.mockResolvedValue(makePlatformPayment({ status: 'RECORDED' }));
    renderWithProviders(<PaymentsPage />, { permissions: MANAGE });
    await user.click(await screen.findByRole('button', { name: 'Record payment' }));
    const dialog = screen.getByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Tenant/ }));
    await user.click(await screen.findByRole('option', { name: 'Kilimanjaro Plant Hire' }));
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.type(within(dialog).getByRole('textbox', { name: /Reference/ }), 'CRDB-9');
    await user.type(within(dialog).getByRole('textbox', { name: /Amount/ }), '250000.50');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    expect(await within(dialog).findByText(/Oldest open invoices/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Record payment' }));
    await waitFor(() => {
      expect(pay.record).toHaveBeenCalledTimes(1);
    });
    const [body] = pay.record.mock.calls[0] ?? [];
    expect(body).toMatchObject({
      tenant_id: 'tenant-1',
      amount: '250000.50',
      currency: 'TZS',
      reference: 'CRDB-9',
    });
    expect(body).not.toHaveProperty('invoice_id');
  });

  it('allocates unallocated money to chosen lines, within payable and unallocated', async () => {
    const user = userEvent.setup();
    pay.allocate.mockResolvedValue({ ...RELEASED, unallocated: '20000.00' });
    renderWithProviders(<PaymentsPage />, { permissions: MANAGE });
    await user.click(await screen.findByRole('button', { name: 'Allocate' }));
    const dialog = screen.getByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Invoice/ }));
    await user.click(await screen.findByRole('option', { name: /AST-2026-0000007/ }));
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    const sms = within(dialog).getByRole('textbox', { name: 'Amount for line 1' });
    const sub = within(dialog).getByRole('textbox', { name: 'Amount for line 2' });
    await user.type(sms, '100000.01');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    expect(
      await within(dialog).findByText(/At most TZS 100,000.00 is still payable/),
    ).toBeVisible();
    await user.clear(sms);
    await user.type(sms, '100000');
    await user.type(sub, '30000');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    expect(
      await within(dialog).findByText(/The lines total more than the TZS 120,000.00 unallocated/),
    ).toBeVisible();
    await user.clear(sub);
    await user.type(sub, '20000');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Allocate' }));
    await waitFor(() => {
      expect(pay.allocate).toHaveBeenCalledWith(
        'pay-2',
        {
          allocations: [
            { line_id: 'l-sms', amount: '100000' },
            { line_id: 'l-sub', amount: '20000' },
          ],
        },
        expect.any(String),
      );
    });
    expect(await screen.findByText('Payment allocated.')).toBeInTheDocument();
  });

  it('allocates to the oldest open invoices when no invoice is chosen', async () => {
    const user = userEvent.setup();
    pay.allocate.mockResolvedValue({ ...RELEASED, unallocated: '0.00' });
    renderWithProviders(<PaymentsPage />, { permissions: MANAGE });
    await user.click(await screen.findByRole('button', { name: 'Allocate' }));
    const dialog = screen.getByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Allocate' }));
    await waitFor(() => {
      expect(pay.allocate).toHaveBeenCalledWith('pay-2', {}, expect.any(String));
    });
  });
});
