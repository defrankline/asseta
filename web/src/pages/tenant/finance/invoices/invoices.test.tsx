import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../../access/permissionCodes';
import { ApiError } from '../../../../api/ApiError';
import type { customerService } from '../../../../api/services/customerService';
import type {
  customerPaymentService,
  hireInvoiceService,
} from '../../../../api/services/financeService';
import type { jobService } from '../../../../api/services/jobService';
import { CUSTOMER, makeInvoice, makePayment, page } from '../../../../test/financeFixtures';
import { CONTRACT, makeJob, makeSummary } from '../../../../test/jobFixtures';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { HireInvoiceDetailPage } from './HireInvoiceDetailPage';
import { InvoicesTab } from './InvoicesTab';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof hireInvoiceService.list>(),
  get: vi.fn<typeof hireInvoiceService.get>(),
  createDraft: vi.fn<typeof hireInvoiceService.createDraft>(),
  issue: vi.fn<typeof hireInvoiceService.issue>(),
  void: vi.fn<typeof hireInvoiceService.void>(),
  payments: vi.fn<typeof customerPaymentService.list>(),
  customers: vi.fn<typeof customerService.list>(),
  getCustomer: vi.fn<typeof customerService.get>(),
  contracts: vi.fn<typeof customerService.listContracts>(),
  jobs: vi.fn<typeof jobService.list>(),
  summary: vi.fn<typeof jobService.summary>(),
}));
vi.mock('../../../../api/services/financeService', () => ({
  hireInvoiceService: {
    list: mocks.list,
    get: mocks.get,
    createDraft: mocks.createDraft,
    issue: mocks.issue,
    void: mocks.void,
  },
  customerPaymentService: { list: mocks.payments },
}));
vi.mock('../../../../api/services/customerService', () => ({
  customerService: {
    list: mocks.customers,
    get: mocks.getCustomer,
    listContracts: mocks.contracts,
  },
}));
vi.mock('../../../../api/services/jobService', () => ({
  jobService: { list: mocks.jobs, summary: mocks.summary },
}));
vi.mock('../../../../api/services/machineService', () => ({
  machineService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 }),
  },
}));

const READ = [P.tenantFinanceRead, P.tenantCustomerRead];
const WRITE = [...READ, P.tenantFinanceInvoice, P.tenantFinancePayment];
const CHARGES = {
  currency: 'TZS',
  lines: [],
  subtotal: '1200000',
  discount_total: '0',
  tax_total: '216000',
  total: '1416000',
};
const BILLABLE = makeSummary({
  job: makeJob({ id: 'job-ok', job_number: 'J-OK', status: 'COMPLETED' }),
  billing_ready: true,
  blocking_exceptions: 0,
  charges: CHARGES,
});
const BLOCKED = makeSummary({
  job: makeJob({ id: 'job-blocked', job_number: 'J-BLOCKED', status: 'COMPLETED' }),
});

beforeEach(() => {
  mocks.list.mockResolvedValue(page([makeInvoice()]));
  mocks.customers.mockResolvedValue(page([CUSTOMER]));
  mocks.getCustomer.mockResolvedValue(CUSTOMER);
  mocks.contracts.mockResolvedValue(page([CONTRACT]));
  mocks.jobs.mockResolvedValue(page([BILLABLE.job, BLOCKED.job]));
  mocks.summary.mockImplementation((id) => Promise.resolve(id === 'job-ok' ? BILLABLE : BLOCKED));
  mocks.payments.mockResolvedValue(page([]));
});

function renderDetail(permissions: string[], accessState: 'FULL' | 'READ_ONLY' = 'FULL') {
  renderWithProviders(
    <Routes>
      <Route path="/tenant/finance/invoices/:invoiceId" element={<HireInvoiceDetailPage />} />
    </Routes>,
    {
      tenantPermissions: permissions,
      accessState,
      route: '/tenant/finance/invoices/ffffffff-0000-4000-8000-000000000001',
    },
  );
}

describe('InvoicesTab', () => {
  it('lists invoices with currency and filters by status and server-searched customer', async () => {
    const user = userEvent.setup();
    renderWithProviders(<InvoicesTab timeZone="UTC" />, { tenantPermissions: READ });
    expect(await screen.findByText('HINV-2026-00001')).toBeInTheDocument();
    expect(screen.getByText('TZS 1,416,000.00')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New invoice' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: 'Customer' }));
    await user.type(screen.getByRole('combobox', { name: 'Customer' }), 'acm');
    await waitFor(() => {
      expect(mocks.customers).toHaveBeenCalledWith(
        expect.objectContaining({ q: 'acm' }),
        expect.any(AbortSignal),
      );
    });
    await user.click(await screen.findByRole('option', { name: 'ACME · Acme Builders' }));
    await waitFor(() => {
      expect(mocks.list.mock.lastCall?.[0].filters?.customer_id).toBe(CUSTOMER.id);
    });
  });

  it('drafts an invoice from billing-ready COMPLETED jobs only', async () => {
    const user = userEvent.setup();
    mocks.createDraft.mockResolvedValue(makeInvoice({ status: 'DRAFT', invoice_number: null }));
    renderWithProviders(<InvoicesTab timeZone="UTC" />, { tenantPermissions: WRITE });
    await user.click(await screen.findByRole('button', { name: 'New invoice' }));
    await user.click(screen.getByRole('combobox', { name: /Customer/ }));
    await user.click(await screen.findByRole('option', { name: 'ACME · Acme Builders' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    const ok = await screen.findByRole('checkbox', { name: 'Invoice job J-OK' });
    expect(screen.getByRole('checkbox', { name: 'Invoice job J-BLOCKED' })).toBeDisabled();
    expect(mocks.jobs).toHaveBeenCalledWith(
      expect.objectContaining({ filters: { status: 'COMPLETED' } }),
      expect.any(AbortSignal),
    );
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Pick at least one billing-ready job')).toBeInTheDocument();
    await user.click(ok);
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText(/J-OK/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create draft' }));
    await waitFor(() => {
      expect(mocks.createDraft).toHaveBeenCalledWith(
        { customer_id: CUSTOMER.id, job_ids: ['job-ok'], notes: null },
        expect.any(String),
      );
    });
  });
});

describe('HireInvoiceDetailPage', () => {
  it('voids only with a reason and explains the reversal', async () => {
    const user = userEvent.setup();
    mocks.get.mockResolvedValue(makeInvoice());
    mocks.void.mockResolvedValue(makeInvoice({ status: 'VOIDED', void_reason: 'Wrong rate' }));
    renderDetail(WRITE);
    await user.click(await screen.findByRole('button', { name: 'Void (reverse)' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/records a reversal of/)).toBeInTheDocument();
    expect(
      within(dialog).getByText(/released back to the customer as unallocated credit/),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Void invoice' }));
    expect(await within(dialog).findByText('A reason is required')).toBeInTheDocument();
    expect(mocks.void).not.toHaveBeenCalled();
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'Wrong rate');
    await user.click(within(dialog).getByRole('button', { name: 'Void invoice' }));
    await waitFor(() => {
      expect(mocks.void).toHaveBeenCalledWith(
        'ffffffff-0000-4000-8000-000000000001',
        { reason: 'Wrong rate' },
        expect.any(String),
      );
    });
  });

  it('keeps DRAFT_STALE from issuing in the dialog with its hint', async () => {
    const user = userEvent.setup();
    mocks.get.mockResolvedValue(
      makeInvoice({ status: 'DRAFT', invoice_number: null, issued_at: null, payment_state: null }),
    );
    mocks.issue.mockRejectedValue(
      new ApiError({
        status: 409,
        code: 'DRAFT_STALE',
        message: 'Job charges changed',
        correlationId: 'c',
      }),
    );
    renderDetail(WRITE);
    await user.click(await screen.findByRole('button', { name: 'Issue invoice' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Issue invoice' }));
    expect(
      await within(dialog).findByText(
        /^DRAFT_STALE: Job charges changed — Job charges changed since drafting/,
      ),
    ).toBeInTheDocument();
  });

  it('shows allocated payments with their status and hides commands while READ_ONLY', async () => {
    mocks.get.mockResolvedValue(makeInvoice());
    mocks.payments.mockResolvedValue(
      page([
        makePayment({
          status: 'VERIFIED',
          allocations: [
            {
              id: 'al-1',
              invoice_id: 'ffffffff-0000-4000-8000-000000000001',
              amount: '400000.0000',
              created_at: '2026-10-21T09:05:00Z',
              released_at: null,
              release_reason: null,
            },
          ],
        }),
      ]),
    );
    renderDetail(WRITE, 'READ_ONLY');
    const table = await screen.findByRole('table', { name: 'Payments allocated' });
    expect(within(table).getByText('Verified')).toBeInTheDocument();
    expect(within(table).getByText('TZS 400,000.00')).toBeInTheDocument();
    expect(screen.getByText('Balance due')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Void (reverse)' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Record payment' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Print view' })).toBeInTheDocument();
  });
});
