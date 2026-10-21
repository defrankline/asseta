/**
 * Server lookups for finance pickers. Every `search*` passes the typed text to the API (`q`) and asks
 * for one page (LOOKUP_PAGE_SIZE); results are never filtered in the browser.
 */
import { customerService } from '../../../api/services/customerService';
import { expenseCategoryService } from '../../../api/services/expenseCategoryService';
import { expenseService } from '../../../api/services/expenseService';
import { hireInvoiceService } from '../../../api/services/financeService';
import { jobService } from '../../../api/services/jobService';
import { machineService } from '../../../api/services/machineService';
import { staffService } from '../../../api/services/staffService';
import type {
  CustomerDto,
  ExpenseCategoryDto,
  ExpenseDto,
  HireInvoiceDto,
  JobDto,
  MachineDto,
  StaffDto,
} from '../../../api/types';
import { LOOKUP_PAGE_SIZE } from '../../../components/data/AsyncAutocomplete';
import { formatMoney } from '../../../utils/money';
import { machineLabel } from './display';

const one = (q: string) => ({ page: 1, page_size: LOOKUP_PAGE_SIZE, q });

export const customerOptionLabel = (c: CustomerDto): string => `${c.code} · ${c.name}`;
export const searchCustomers = async (q: string, signal: AbortSignal) =>
  (await customerService.list(one(q), signal)).items;
export const resolveCustomer = (id: string, signal: AbortSignal) => customerService.get(id, signal);

export const staffOptionLabel = (s: StaffDto): string => s.full_name;
export const searchStaff = async (q: string, signal: AbortSignal) =>
  (await staffService.list(one(q), signal)).items;
export const searchSupervisors = async (q: string, signal: AbortSignal) =>
  (await staffService.list({ ...one(q), filters: { kind: 'SUPERVISOR' } }, signal)).items;
export const resolveStaff = (id: string, signal: AbortSignal) => staffService.get(id, signal);

export const machineOptionLabel = (m: MachineDto): string => machineLabel(m);
export const searchMachines = async (q: string, signal: AbortSignal) =>
  (await machineService.list(one(q), signal)).items;
export const resolveMachine = (id: string, signal: AbortSignal) => machineService.get(id, signal);

export const jobOptionLabel = (j: JobDto): string => `${j.job_number} · ${j.status}`;
export const searchJobs = async (q: string, signal: AbortSignal) =>
  (await jobService.list(one(q), signal)).items;
export const resolveJob = async (id: string, signal: AbortSignal) =>
  (await jobService.summary(id, signal)).job;

export const expenseCategoryOptionLabel = (c: ExpenseCategoryDto): string =>
  `${c.code} · ${c.name}`;
export const searchExpenseCategories = (q: string, signal: AbortSignal) =>
  expenseCategoryService.list(signal, q);
export const resolveExpenseCategory = (id: string, signal: AbortSignal) =>
  expenseCategoryService.get(id, signal);

export const expenseOptionLabel = (e: ExpenseDto): string =>
  `${e.description} · ${formatMoney(e.amount, e.currency)}`;
export const searchExpenses = async (q: string, signal: AbortSignal) =>
  (await expenseService.list(one(q), signal)).items;
export const resolveExpense = (id: string, signal: AbortSignal) => expenseService.get(id, signal);

export const invoiceOptionLabel = (i: HireInvoiceDto): string =>
  `${i.invoice_number ?? 'Draft'} · open ${formatMoney(i.balance, i.currency)}`;
/** Issued invoices of one customer (server filters), searched by invoice number. */
export const searchIssuedInvoices =
  (customerId: string) =>
  async (q: string, signal: AbortSignal): Promise<HireInvoiceDto[]> =>
    (
      await hireInvoiceService.list(
        { ...one(q), filters: { status: 'ISSUED', customer_id: customerId } },
        signal,
      )
    ).items;
