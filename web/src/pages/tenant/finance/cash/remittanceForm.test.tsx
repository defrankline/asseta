import { screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../../access/permissionCodes';
import { ApiError } from '../../../../api/ApiError';
import type { DepositAccountDto } from '../../../../api/custodyTypes';
import type { cashService } from '../../../../api/services/cashService';
import type { depositAccountService } from '../../../../api/services/depositAccountService';
import type { policyService } from '../../../../api/services/policyService';
import { makeHandover, page } from '../../../../test/financeFixtures';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { HandoverDialog } from './CashDialogs';
import { RemittanceDecisionDialog } from './CustodyDialogs';
import {
  handoverSchemaFor,
  NO_REMITTANCE_REQUIREMENTS,
  remittanceRequirements,
  toHandoverPayload,
  type HandoverValues,
} from './cashForms';

const m = vi.hoisted(() => ({
  recordHandover: vi.fn<typeof cashService.recordHandover>(),
  uploadRemittanceEvidence: vi.fn<typeof cashService.uploadRemittanceEvidence>(),
  remittanceEvidenceUrl: vi.fn<typeof cashService.remittanceEvidenceUrl>(),
  effective: vi.fn<typeof policyService.effective>(),
  list: vi.fn<typeof depositAccountService.list>(),
  get: vi.fn<typeof depositAccountService.get>(),
}));
vi.mock('../../../../api/services/cashService', () => ({
  cashService: {
    recordHandover: m.recordHandover,
    uploadRemittanceEvidence: m.uploadRemittanceEvidence,
    remittanceEvidenceUrl: m.remittanceEvidenceUrl,
  },
}));
vi.mock('../../../../api/services/policyService', () => ({
  policyService: { effective: m.effective },
}));
vi.mock('../../../../api/services/depositAccountService', () => ({
  depositAccountService: { list: m.list, get: m.get },
  DEPOSIT_ACCOUNT_TYPES: ['BANK', 'MOBILE_MONEY', 'CASH_OFFICE'],
}));

const ACCOUNT: DepositAccountDto = {
  id: 'dddddddd-0000-4000-8000-000000000001',
  name: 'CRDB main',
  account_type: 'BANK',
  institution: 'CRDB',
  account_number_masked: '•••• 4821',
  currency: 'TZS',
  note: null,
  is_active: true,
  version: 1,
  created_at: '2026-10-20T08:00:00Z',
  created_by: null,
  created_by_name: null,
  updated_at: '2026-10-20T08:00:00Z',
  deactivated_at: null,
  deactivated_by: null,
  deactivated_by_name: null,
  deactivation_reason: null,
};

const ALL_ON = {
  enabled: true,
  remittance_reference_required: true,
  remittance_evidence_required: true,
  remittance_account_required: true,
};

function policy(values: Record<string, unknown>) {
  m.effective.mockResolvedValue({
    policy_type: 'CASH_CUSTODY',
    version_stamp: 'v2',
    values,
  } as unknown as Awaited<ReturnType<typeof policyService.effective>>);
}

function renderDialog(permissions: string[] = [P.tenantCollectionRecord]) {
  const onRecorded = vi.fn();
  renderWithProviders(
    <HandoverDialog ownCustody timeZone="UTC" onClose={vi.fn()} onRecorded={onRecorded} />,
    { tenantPermissions: permissions },
  );
  return onRecorded;
}

async function pick(user: UserEvent, label: RegExp, option: string | RegExp) {
  await user.click(screen.getByRole('combobox', { name: label }));
  await user.click(await screen.findByRole('option', { name: option }));
}

async function toDeposit(user: UserEvent) {
  await user.type(screen.getByRole('textbox', { name: /Amount/ }), '50000');
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByRole('combobox', { name: /How was it paid/ });
}

beforeEach(() => {
  m.list.mockResolvedValue(page([ACCOUNT]));
  m.get.mockResolvedValue(ACCOUNT);
  m.uploadRemittanceEvidence.mockResolvedValue({
    id: 'aaaaaaaa-0000-4000-8000-000000000001',
    sha256: 'abc123abc123abc123',
    content_type: 'image/jpeg',
    size_bytes: 1200,
    purpose: 'REMITTANCE_EVIDENCE',
    uploaded_at: '2026-10-21T15:00:00Z',
  });
  m.recordHandover.mockResolvedValue(makeHandover());
});

describe('remittance requirements', () => {
  it('reads every switch as off while the cash custody controls are off', () => {
    expect(remittanceRequirements({ ...ALL_ON, enabled: false })).toEqual(
      NO_REMITTANCE_REQUIREMENTS,
    );
    expect(remittanceRequirements(null)).toEqual(NO_REMITTANCE_REQUIREMENTS);
    expect(remittanceRequirements(ALL_ON)).toEqual({
      reference: true,
      evidence: true,
      account: true,
    });
  });

  it('never asks for a reference when cash is handed to the office', () => {
    const schema = handoverSchemaFor({ reference: true, evidence: false, account: false });
    const base: HandoverValues = {
      staff_member_id: '',
      amount: '100',
      currency: '',
      method: 'CASH_TO_OFFICE',
      deposit_account_id: '',
      reference: '',
      evidence: [],
      handed_at: '2026-10-21T15:00:00Z',
      note: '',
    };
    expect(schema.isValidSync(base)).toBe(true);
    expect(schema.isValidSync({ ...base, method: 'MOBILE_MONEY' })).toBe(false);
    expect(schema.isValidSync({ ...base, method: 'MOBILE_MONEY', reference: 'MP123' })).toBe(true);
  });

  it('sends method, account, reference and photo ids', () => {
    const body = toHandoverPayload(
      {
        staff_member_id: '',
        amount: ' 100 ',
        currency: 'TZS',
        method: 'BANK_DEPOSIT',
        deposit_account_id: ACCOUNT.id,
        reference: ' TX1 ',
        evidence: [{ id: 'a1' } as never, { id: 'a2' } as never],
        handed_at: '2026-10-21T15:00:00Z',
        note: '',
      },
      'client-1',
    );
    expect(body).toMatchObject({
      amount: '100',
      method: 'BANK_DEPOSIT',
      deposit_account_id: ACCOUNT.id,
      reference: 'TX1',
      evidence_attachment_ids: ['a1', 'a2'],
      client_id: 'client-1',
    });
  });
});

describe('HandoverDialog (record remittance)', () => {
  it('explains the switched-on requirements and blocks until they are met', async () => {
    const user = userEvent.setup();
    policy(ALL_ON);
    renderDialog();
    await toDeposit(user);
    expect(
      await screen.findByText(/Your organisation requires the company account the money was paid/),
    ).toBeInTheDocument();
    await pick(user, /How was it paid/, 'Bank deposit');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(
      await screen.findByText(
        'Your organisation requires the company account the money was paid into',
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Your organisation requires the transaction reference for bank and mobile-money remittances',
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Your organisation requires a photo of the deposit slip or payment confirmation',
      ),
    ).toBeInTheDocument();
    expect(m.recordHandover).not.toHaveBeenCalled();
  });

  it('records a bank remittance with its account, reference and photo', async () => {
    const user = userEvent.setup();
    policy(ALL_ON);
    const onRecorded = renderDialog();
    await toDeposit(user);
    await pick(user, /How was it paid/, 'Bank deposit');
    const account = screen.getByRole('combobox', { name: /Company account/ });
    await user.click(account);
    await user.type(account, 'crdb');
    await user.click(await screen.findByRole('option', { name: /CRDB main · •••• 4821 · TZS/ }));
    await waitFor(() => {
      expect(m.list).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({ account_type: 'BANK' }) as unknown,
        }),
        expect.any(AbortSignal),
      );
    });
    await user.type(screen.getByRole('textbox', { name: /Transaction reference/ }), 'TX-77');
    await user.upload(
      screen.getByLabelText('Add photo'),
      new File(['x'], 'slip.jpg', { type: 'image/jpeg' }),
    );
    expect(await screen.findByText('Photo 1')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Next' }));
    expect(await screen.findByText('CRDB main · •••• 4821 · TZS')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Record remittance' }));
    await waitFor(() => {
      expect(onRecorded).toHaveBeenCalled();
    });
    expect(m.recordHandover.mock.lastCall?.[0]).toMatchObject({
      amount: '50000',
      currency: 'TZS',
      method: 'BANK_DEPOSIT',
      deposit_account_id: ACCOUNT.id,
      reference: 'TX-77',
      evidence_attachment_ids: ['aaaaaaaa-0000-4000-8000-000000000001'],
    });
  });

  it('shows a server refusal code in plain words', async () => {
    const user = userEvent.setup();
    // The office user cannot read the policy: nothing is enforced client-side, the server explains.
    renderDialog([P.tenantFinanceCash]);
    m.recordHandover.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'REMITTANCE_EVIDENCE_REQUIRED',
        message: 'Attach a photo of the deposit slip or payment confirmation',
        correlationId: null,
      }),
    );
    await toDeposit(user);
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Record remittance' }));
    expect(
      await screen.findByText(/Add the photo under Deposit/, { exact: false }),
    ).toBeInTheDocument();
    expect(m.effective).not.toHaveBeenCalled();
  });
});

describe('RemittanceDecisionDialog', () => {
  it('shows the account, reference and photos next to the amount received', async () => {
    const user = userEvent.setup();
    m.remittanceEvidenceUrl.mockResolvedValue({
      url: 'https://store.test/slip.jpg',
      expires_in_seconds: 300,
    });
    const h = makeHandover({
      method: 'MOBILE_MONEY',
      deposit_account_id: ACCOUNT.id,
      deposit_account_name: 'M-Pesa till',
      reference: 'MP-123',
      evidence_attachment_ids: ['aaaaaaaa-0000-4000-8000-000000000001'],
    });
    renderWithProviders(
      <RemittanceDecisionDialog
        handover={h}
        custodianName="Sam Supervisor"
        timeZone="UTC"
        onDone={vi.fn()}
        onClose={vi.fn()}
      />,
      { tenantPermissions: [P.tenantFinanceVerify] },
    );
    expect(screen.getByText('Mobile money')).toBeInTheDocument();
    expect(screen.getByText('M-Pesa till')).toBeInTheDocument();
    expect(screen.getByText('MP-123')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'View photo 1' }));
    await waitFor(() => {
      expect(m.remittanceEvidenceUrl).toHaveBeenCalledWith(
        h.id,
        'aaaaaaaa-0000-4000-8000-000000000001',
      );
    });
    await pick(user, /Decision/, /Confirm/);
    expect(screen.getByRole('textbox', { name: /Amount received/ })).toBeInTheDocument();
  });
});
