import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { BookedJobDto, HoursPurchaseDto, HoursQuoteDto } from '../../../api/hoursTypes';
import type { hoursRequestService, hoursService } from '../../../api/services/hoursService';
import { hoursPurchaseSchema } from '../../../api/services/hoursSchemas';
import { jobSchema } from '../../../api/services/jobSchemas';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { HOURS_ROUTES } from '../../../navigation/hoursRoutes';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { BookedJobCell } from './BookedJob';
import { HoursPurchaseDetailPage } from './HoursPurchaseDetailPage';
import {
  bookedJobStatusLabel,
  emptyPurchaseValues,
  purchaseRecordedText,
  purchaseSchema,
  toPurchasePayload,
} from './purchaseForm';
import { RecordPurchaseDialog } from './RecordPurchaseDialog';

const mocks = vi.hoisted(() => ({
  quote: vi.fn<typeof hoursService.quotePurchase>(),
  record: vi.fn<typeof hoursService.recordPurchase>(),
  getPurchase: vi.fn<typeof hoursService.getPurchase>(),
  listTransfers: vi.fn<typeof hoursRequestService.listTransfers>(),
  listCancellations: vi.fn<typeof hoursRequestService.listCancellations>(),
  contractCustomer: vi.fn<(id: string) => void>(),
}));
vi.mock('../../../api/services/hoursService', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  hoursService: {
    quotePurchase: mocks.quote,
    recordPurchase: mocks.record,
    getPurchase: mocks.getPurchase,
    uploadEvidence: vi.fn(),
  },
  hoursRequestService: {
    listTransfers: mocks.listTransfers,
    listCancellations: mocks.listCancellations,
  },
}));
// Plain inputs stand in for the async pickers and the date-time picker (their own tests cover them).
vi.mock('../shared/financePickers', () => {
  const Plain = ({ name, label }: { name: string; label: string }) => (
    <FormikTextField name={name} label={label} />
  );
  return {
    FormikCustomerIdPicker: Plain,
    FormikMachineIdPicker: Plain,
    FormikStaffIdPicker: Plain,
  };
});
vi.mock('../shared/lookupPickers', () => ({ FormikJobSitePicker: () => null }));
vi.mock('../../../components/forms/FormikDateTimeField', () => ({
  FormikDateTimeField: ({ name, label }: { name: string; label: string }) => (
    <FormikTextField name={name} label={label} />
  ),
}));
vi.mock('./hoursPickers', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  FormikCustomerContractPicker: ({
    name,
    label,
    helperText,
    customerId,
  }: {
    name: string;
    label: string;
    helperText: string;
    customerId: string;
  }) => {
    mocks.contractCustomer(customerId);
    return <FormikTextField name={name} label={label} helperText={helperText} />;
  },
}));

const QUOTE: HoursQuoteDto = {
  machine_id: 'm1',
  customer_id: 'c1',
  hours: '6',
  hourly_rate: '95000.0000',
  discount_percent: '0',
  effective_rate: '95000.0000',
  amount: '570000.0000',
  currency: 'TZS',
  minimum_hours: '1',
};

const JOB: BookedJobDto = {
  id: 'j1',
  job_number: 'JOB-2026-00042',
  status: 'PENDING_APPROVAL',
  contract_id: 'k1',
  contract_number: 'CTR-0007',
  planned_start: '2026-11-12T05:00:00Z',
  planned_end: '2026-11-12T13:00:00Z',
  approved_at: null,
};

const BASE = ['tenant.hours.purchase', 'tenant.collection.record'];

function open(perms: string[], onRecorded = vi.fn()) {
  renderWithProviders(
    <RecordPurchaseDialog
      timeZone="UTC"
      field
      walkInAllowed={false}
      onClose={vi.fn()}
      onRecorded={onRecorded}
    />,
    { tenantPermissions: [...BASE, ...perms] },
  );
}

async function toHoursStep(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Customer'), 'c1');
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await user.type(screen.getByLabelText('Machine'), 'm1');
  await user.type(screen.getByLabelText(/Hours bought/), '6');
  await screen.findByText('Total: TZS 570,000 (6 h × 95,000/h)');
}

beforeEach(() => {
  mocks.quote.mockReset().mockResolvedValue(QUOTE);
  mocks.record.mockReset();
  mocks.contractCustomer.mockReset();
});

describe('Record purchase: book the job', () => {
  it('is not offered without tenant.job.request', async () => {
    const user = userEvent.setup();
    open([]);
    await toHoursStep(user);
    expect(screen.queryByRole('switch', { name: 'Book the job' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Next' }));
    await screen.findByRole('button', { name: 'Record purchase' });
    expect(screen.queryByText('Job contract')).not.toBeInTheDocument();
  });

  it('books the job with the sale, checks the window and reports the job number', async () => {
    const onRecorded = vi.fn();
    mocks.record.mockResolvedValue({
      id: 'p1',
      purchase_number: 'HP-1',
      job: JOB,
    } as HoursPurchaseDto);
    const user = userEvent.setup();
    open(['tenant.job.request'], onRecorded);
    await toHoursStep(user);
    await user.click(screen.getByRole('switch', { name: 'Book the job' }));
    expect(screen.getByText("Leave empty to use the customer's contract")).toBeInTheDocument();
    expect(mocks.contractCustomer).toHaveBeenLastCalledWith('c1');

    // The start is required once booking.
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Enter when the job starts')).toBeInTheDocument();

    await user.type(screen.getByLabelText(/Job starts/), '2026-11-12T05:00:00Z');
    await user.type(screen.getByLabelText(/Job ends/), '2026-11-12T04:00:00Z');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('The end must be after the start')).toBeInTheDocument();
    await user.clear(screen.getByLabelText(/Job ends/));
    await user.type(screen.getByLabelText(/Job ends/), '2026-11-12T13:00:00Z');
    await user.type(screen.getByLabelText(/Job note/), 'Level the plot');

    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Next' }));
    await screen.findByRole('button', { name: 'Record purchase' });
    expect(screen.getByText('Job contract')).toBeInTheDocument();
    expect(screen.getByText("The customer's contract")).toBeInTheDocument();
    expect(screen.getByText('Level the plot')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Record purchase' }));
    await waitFor(() => {
      expect(onRecorded).toHaveBeenCalled();
    });
    expect(mocks.record.mock.calls[0]?.[0].job).toEqual({
      planned_start: '2026-11-12T05:00:00Z',
      planned_end: '2026-11-12T13:00:00Z',
      job_site_id: null,
      contract_id: null,
      note: 'Level the plot',
    });
  });

  it('shows the booking refusal in plain words', async () => {
    mocks.record.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'CONTRACT_CHOICE_REQUIRED',
        message: 'Several contracts',
        correlationId: 'c-1',
      }),
    );
    const user = userEvent.setup();
    open(['tenant.job.request']);
    await toHoursStep(user);
    await user.click(screen.getByRole('switch', { name: 'Book the job' }));
    await user.type(screen.getByLabelText(/Job starts/), '2026-11-12T05:00:00Z');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Record purchase' }));
    expect(
      await screen.findByText(/several contracts; choose the contract for the job/),
    ).toBeInTheDocument();
  });
});

describe('sale booking payload and messages', () => {
  it('sends no job unless booking, and no contract for a walk-in', () => {
    const v = { ...emptyPurchaseValues(), customer_id: 'c1', machine_id: 'm1', hours: '2' };
    expect(toPurchasePayload(v, 'x', { field: true }).job).toBeNull();
    const walkIn = {
      ...v,
      customer_mode: 'WALK_IN' as const,
      walk_in_name: 'Juma',
      book_job: true,
      job_start: '2026-11-12T05:00:00Z',
      job_contract_id: 'k9',
    };
    expect(toPurchasePayload(walkIn, 'x', { field: true }).job).toEqual({
      planned_start: '2026-11-12T05:00:00Z',
      planned_end: null,
      job_site_id: null,
      contract_id: null,
      note: null,
    });
    expect(purchaseSchema.isValidSync({ ...walkIn, payments: [] })).toBe(true);
  });

  it('names the booked job and its status in the success message', () => {
    expect(purchaseRecordedText({ purchase_number: 'HP-1', job: null })).toBe(
      'Hours purchase HP-1 recorded.',
    );
    expect(purchaseRecordedText({ purchase_number: 'HP-1', job: JOB })).toBe(
      'Hours purchase HP-1 recorded. Job JOB-2026-00042 booked (waiting for approval).',
    );
    expect(bookedJobStatusLabel({ status: 'APPROVED' })).toBe('Approved');
  });

  it('accepts job and hours_purchase_id in responses', () => {
    expect(hoursPurchaseSchema.isValidSync({ ...PURCHASE, job: JOB })).toBe(true);
    expect(hoursPurchaseSchema.isValidSync({ ...PURCHASE, job: { id: 'j1' } })).toBe(false);
    expect(jobSchema.describe()).toHaveProperty('fields.hours_purchase_id');
  });
});

describe('booked job display', () => {
  it('lists the job number linking to the job with its status', () => {
    renderWithProviders(<BookedJobCell job={{ ...JOB, status: 'APPROVED' }} />);
    expect(screen.getByRole('link', { name: 'JOB-2026-00042' })).toHaveAttribute(
      'href',
      '/tenant/jobs/j1',
    );
    expect(screen.getByText('Approved')).toBeInTheDocument();
  });

  it('shows the booked job on the purchase', async () => {
    mocks.getPurchase.mockResolvedValue({ ...PURCHASE, job: JOB });
    const empty = { items: [], total: 0, page: 1, page_size: 100 };
    mocks.listTransfers.mockResolvedValue(empty);
    mocks.listCancellations.mockResolvedValue(empty);
    renderWithProviders(
      <Routes>
        <Route path={HOURS_ROUTES.purchaseDetail} element={<HoursPurchaseDetailPage />} />
      </Routes>,
      { tenantPermissions: ['tenant.hours.read'], route: '/tenant/hours/purchases/p1' },
    );
    expect(await screen.findByRole('heading', { name: 'Booked job' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'JOB-2026-00042' })).toHaveAttribute(
      'href',
      '/tenant/jobs/j1',
    );
    expect(screen.getByText('Waiting for approval')).toBeInTheDocument();
    expect(screen.getByText('CTR-0007')).toBeInTheDocument();
    expect(screen.getByText(/12 Nov 2026.*–.*/)).toBeInTheDocument();
  });
});

const PURCHASE = {
  id: 'p1',
  purchase_number: 'HP-2026-00007',
  customer_id: 'c1',
  customer_kind: 'REGISTERED',
  customer_name: 'Juma Construction',
  machine_id: 'm1',
  machine_code: 'EX-01',
  machine_name: 'Excavator',
  job_site_id: null,
  hours: '20',
  currency: 'TZS',
  rate_card_id: 'rc1',
  hourly_rate: '50000',
  discount_id: null,
  discount_percent: '0',
  effective_rate: '50000',
  amount: '1000000',
  status: 'ACTIVE',
  source: 'WEB',
  note: null,
  policy_version: 'v1',
  client_id: null,
  created_at: '2026-10-02T08:00:00Z',
  created_by: null,
  cancellation_id: null,
  cancelled_at: null,
  allocations: [],
  payment: null,
  machines: [],
  totals: {
    purchased: '20',
    activated: '20',
    activated_from_payments: '20',
    activated_on_credit: '0',
    awaiting_activation: '0',
    consumed: '0',
    expired: '0',
    remaining: '20',
    reversed: '0',
    transferred: '0',
    provisional: '0',
    refunded: '0',
    corrected: '0',
    amount_claimed_unverified: '0',
    amount_outstanding: '0',
    amount_verified: '1000000',
  },
} as HoursPurchaseDto;
