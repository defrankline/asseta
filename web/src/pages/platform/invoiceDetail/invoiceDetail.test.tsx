import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import { PlatformInvoicingServiceContext } from '../../../api/services/platformInvoicingService';
import {
  fakePlatformInvoicingService,
  makeInvoice,
  makePlatformPayment,
  type FakePlatformInvoicingService,
} from '../../../test/fakePlatformInvoicingService';
import { fakeSocketServer, type FakeSocketServer } from '../../../test/fakeWebSocket';
import { acceptSocket, LiveProviders, push } from '../../../test/realtimeHarness';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { PlatformSmsWalletsPage, TenantSmsWalletPage } from '../smsWallet/SmsWalletPages';
import { PlatformInvoiceDetailPage } from './PlatformInvoiceDetailPage';

vi.mock('../shared/platformLookups', () => ({
  tenantLabel: (t: { display_name: string }) => t.display_name,
  searchTenants: () =>
    Promise.resolve([{ id: 'tenant-1', display_name: 'Kilimanjaro Plant Hire' }]),
}));

let fake: FakePlatformInvoicingService;
let server: FakeSocketServer;
const READ = [P.platformInvoiceRead, P.platformPaymentRead];

function renderDetail(permissions: string[]) {
  return renderWithProviders(
    <LiveProviders server={server}>
      <PlatformInvoicingServiceContext.Provider value={fake}>
        <Routes>
          <Route path="/platform/invoices/:invoiceId" element={<PlatformInvoiceDetailPage />} />
        </Routes>
      </PlatformInvoicingServiceContext.Provider>
    </LiveProviders>,
    { permissions, route: '/platform/invoices/inv-1' },
  );
}

const heading = () => screen.findByRole('heading', { name: 'Invoice AST-2026-0000007' });

beforeEach(() => {
  fake = fakePlatformInvoicingService();
  server = fakeSocketServer();
});

describe('PlatformInvoiceDetailPage', () => {
  it('shows kind, per-line payable / paid / fulfilment and the allocation per line', async () => {
    renderDetail(READ);
    await heading();
    expect(screen.getByText('Ad hoc')).toBeInTheDocument();
    const lines = screen.getByRole('table', { name: 'Invoice lines' });
    const [, sms, sub] = within(lines).getAllByRole('row');
    expect(sms).toHaveTextContent('10,000 SMS credits');
    expect(sms).toHaveTextContent('Partially paid');
    expect(sms).toHaveTextContent('Awaiting full payment');
    expect(sub).toHaveTextContent('Unpaid');
    expect(sub).toHaveTextContent('1 Nov 2026 – 30 Nov 2026');
    const payments = await screen.findByRole('table', { name: 'Payments' });
    expect(within(payments).getByText('MPESA-QX81')).toBeInTheDocument();
    expect(
      within(payments).getByText(/SMS bundle 5,000 \(10,000 SMS credits\):/),
    ).toHaveTextContent('TZS 100,000.00');
    expect(screen.getByRole('region', { name: 'Summary' })).toHaveTextContent('TZS 250,000.00');
  });

  it('labels fulfilled and reversal-flagged lines, and released allocations', async () => {
    fake.store.invoice = makeInvoice({
      status: 'VOIDED',
      void_reason: 'Raised in error',
      voided_at: '2026-10-22T10:00:00Z',
      lines: makeInvoice().lines.map((l, i) => ({
        ...l,
        fulfilment_status: i === 0 ? 'REVERSAL_FLAGGED' : 'REVERSED',
      })),
    });
    fake.store.payments = [
      makePlatformPayment({
        allocations: [
          {
            id: 'al-1',
            invoice_id: 'inv-1',
            line_id: null,
            amount: '100000.00',
            created_at: '2026-10-21T10:00:00Z',
            released_at: '2026-10-22T10:00:00Z',
            release_reason: 'Invoice voided: Raised in error',
          },
        ],
        unallocated: '100000.00',
      }),
    ];
    renderDetail(READ);
    await heading();
    expect(screen.getByText('This invoice is void.')).toBeInTheDocument();
    expect(screen.getByText('Reversal flagged for review')).toBeInTheDocument();
    expect(screen.getByText('Reversed')).toBeInTheDocument();
    expect(await screen.findByText(/released .*Invoice voided: Raised in error/)).toBeVisible();
    expect(screen.getByText(/Whole invoice \(lines in order\)/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Void invoice' })).not.toBeInTheDocument();
  });

  it('gates actions by permission and hides payments without payment read', async () => {
    const view = renderDetail([P.platformInvoiceRead]);
    await heading();
    expect(screen.queryByRole('button', { name: 'Void invoice' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Record payment' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Payments and line allocation' })).toBeNull();
    expect(fake.listTenantPayments).not.toHaveBeenCalled();
    view.unmount();
    renderDetail([...READ, P.platformInvoiceVoid, P.platformPaymentManage]);
    await heading();
    expect(screen.getByRole('button', { name: 'Void invoice' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Record payment' })).toBeInTheDocument();
  });

  it('voids with a reason (a reversal) even when money was allocated', async () => {
    const user = userEvent.setup();
    renderDetail([...READ, P.platformInvoiceVoid]);
    await heading();
    await user.click(screen.getByRole('button', { name: 'Void invoice' }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText(/money allocated to it becomes tenant credit/)).toBeVisible();
    await user.click(within(dialog).getByRole('button', { name: 'Void invoice' }));
    expect(await within(dialog).findByText('A reason is required')).toBeInTheDocument();
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'Raised in error');
    await user.click(within(dialog).getByRole('button', { name: 'Void invoice' }));
    await waitFor(() => {
      expect(fake.voidInvoice).toHaveBeenCalledWith(
        'inv-1',
        { reason: 'Raised in error' },
        expect.any(String),
      );
    });
    expect(await screen.findByText('This invoice is void.')).toBeInTheDocument();
    expect(screen.getByText('Reversal flagged for review')).toBeInTheDocument();
  });

  it('refreshes itself when the server announces a change to this invoice', async () => {
    renderDetail(READ);
    await heading();
    await acceptSocket(server);
    fake.store.invoice = makeInvoice({ status: 'PAID', balance: '0.00' });
    push(server, 'entity.changed', { entity: 'platform_invoice', id: 'other' });
    push(server, 'entity.changed', {
      entity: 'platform_invoice',
      id: 'inv-1',
      action: 'fulfilled',
    });
    await waitFor(() => {
      expect(fake.getInvoice).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByRole('region', { name: 'Summary' })).toHaveTextContent('TZS 0.00');
  });
});

describe('SMS wallet views', () => {
  it('shows the balance, a low-balance warning and the ledger', async () => {
    renderWithProviders(
      <PlatformInvoicingServiceContext.Provider value={fake}>
        <TenantSmsWalletPage />
      </PlatformInvoicingServiceContext.Provider>,
      { tenantPermissions: [P.tenantBillingRead] },
    );
    expect(await screen.findByRole('group', { name: 'Available SMS credits' })).toHaveTextContent(
      '420',
    );
    expect(screen.getByText(/Low SMS balance/)).toBeInTheDocument();
    expect(await screen.findByText('+5,000')).toBeInTheDocument();
    expect(screen.getByText('-3')).toBeInTheDocument();
    expect(screen.getByText('AST-2026-0000007 line 1: SMS bundle 5,000')).toBeInTheDocument();
    expect(screen.getByText('SMS sent')).toBeInTheDocument();
    expect(fake.getSmsWallet).toHaveBeenCalledWith(null, expect.any(AbortSignal));
  });

  it('lets platform staff pick a tenant by server search', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <PlatformInvoicingServiceContext.Provider value={fake}>
        <PlatformSmsWalletsPage />
      </PlatformInvoicingServiceContext.Provider>,
      { permissions: [P.platformSmsWalletRead] },
    );
    expect(screen.getByText('Choose a tenant')).toBeInTheDocument();
    expect(fake.getSmsWallet).not.toHaveBeenCalled();
    await user.click(screen.getByRole('combobox', { name: 'Tenant' }));
    await user.click(await screen.findByRole('option', { name: 'Kilimanjaro Plant Hire' }));
    expect(await screen.findByText('+5,000')).toBeInTheDocument();
    expect(fake.getSmsWallet).toHaveBeenCalledWith('tenant-1', expect.any(AbortSignal));
  });
});
