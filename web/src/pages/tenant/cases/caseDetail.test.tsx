import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import { ApiError } from '../../../api/ApiError';
import type { caseService } from '../../../api/services/caseService';
import type { peopleService } from '../../../api/services/peopleService';
import type { CaseSignalDto, RuleCode } from '../../../api/types';
import {
  CASE_ID,
  JOB_ID,
  makeCase,
  makeCaseSignal,
  makeDetail,
  PERSON,
  RULE_EVIDENCE,
} from '../../../test/caseFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { resetPersonDirectory } from '../shared/personDirectory';
import { CaseDetailPage } from './CaseDetailPage';

const mocks = vi.hoisted(() => ({
  get: vi.fn<typeof caseService.get>(),
  assign: vi.fn<typeof caseService.assign>(),
  addNote: vi.fn<typeof caseService.addNote>(),
  resolve: vi.fn<typeof caseService.resolve>(),
  reopen: vi.fn<typeof caseService.reopen>(),
  people: vi.fn<typeof peopleService.list>(),
  search: vi.fn<typeof peopleService.search>(),
  emptyPage: { items: [], total: 0, page: 1, page_size: 200 },
}));
vi.mock('../../../api/services/caseService', () => ({
  caseService: {
    get: mocks.get,
    assign: mocks.assign,
    addNote: mocks.addNote,
    resolve: mocks.resolve,
    reopen: mocks.reopen,
  },
}));
vi.mock('../../../api/services/peopleService', () => ({
  PEOPLE_BATCH: 100,
  peopleService: { list: mocks.people, search: mocks.search },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: { list: vi.fn().mockResolvedValue(mocks.emptyPage) },
}));
vi.mock('../../../api/services/staffService', () => ({
  staffService: { list: vi.fn().mockResolvedValue(mocks.emptyPage) },
}));
vi.mock('../../../api/services/jobService', () => ({
  jobService: { summary: vi.fn().mockRejectedValue(new Error('not needed')) },
}));
vi.mock('../../../api/services/expenseService', () => ({
  expenseService: { get: vi.fn(), receiptUrl: vi.fn() },
}));

const READ = [P.tenantCaseRead, P.tenantDirectoryRead];
const ALL = [...READ, P.tenantCaseManage, P.tenantCaseResolve];

function apiError(code: string, message: string) {
  return new ApiError({ status: 422, code, message, correlationId: null, details: [] });
}

beforeEach(() => {
  resetPersonDirectory();
  mocks.get.mockResolvedValue(makeDetail());
  mocks.people.mockResolvedValue([PERSON]);
  mocks.search.mockResolvedValue([PERSON]);
});
afterEach(() => {
  vi.clearAllMocks();
});

function renderDetail(permissions: string[], accessState: 'FULL' | 'READ_ONLY' = 'FULL') {
  renderWithProviders(
    <Routes>
      <Route path="/tenant/cases/:caseId" element={<CaseDetailPage />} />
    </Routes>,
    { tenantPermissions: permissions, accessState, route: `/tenant/cases/${CASE_ID}` },
  );
}

async function loaded() {
  return screen.findByRole('heading', { name: /CASE-2026-00001/ });
}

describe('CaseDetailPage', () => {
  it('explains every kind of linked evidence in neutral sentences with source links', async () => {
    const rules = Object.keys(RULE_EVIDENCE) as RuleCode[];
    const signals: CaseSignalDto[] = [
      ...rules.map((code, i) =>
        makeCaseSignal({ id: `sig-${String(i)}`, code, evidence: { ...RULE_EVIDENCE[code] } }),
      ),
      makeCaseSignal({
        id: 'sig-meter',
        source_type: 'METER_EXCEPTION',
        code: 'METER_DECREASE',
        evidence: { reading: '90', previous_reading: '120', previous_at: 'yesterday' },
      }),
      makeCaseSignal({
        id: 'sig-alert',
        source_type: 'TRACKING_ALERT',
        code: 'RESTRICTED_AREA_ENTRY',
        evidence: { alert_title: 'Entered quarry B', alert_status: 'OPEN' },
      }),
      makeCaseSignal({
        id: 'sig-sod',
        source_type: 'SOD_EVENT',
        code: 'SEGREGATION_OF_DUTIES_ATTEMPT',
        evidence: { action: 'approve', entity_type: 'expense' },
      }),
    ];
    mocks.get.mockResolvedValue(makeDetail({ case: makeCase({ job_id: JOB_ID }), signals }));
    renderDetail(READ);
    await loaded();
    const evidence = within(screen.getByRole('list', { name: 'Linked evidence' }));
    expect(evidence.getAllByRole('listitem')).toHaveLength(signals.length);
    expect(evidence.getByText(/while no job on the machine was in progress/)).toBeInTheDocument();
    expect(evidence.getByText(/is identical \(SHA-256 abcdef012345…\)/)).toBeInTheDocument();
    expect(evidence.getByText(/30\.000 L per meter hour against an allowance/)).toBeInTheDocument();
    expect(
      evidence.getByText(/above the weekly threshold of TZS 1,000,000\.00/),
    ).toBeInTheDocument();
    expect(evidence.getByText(/has been held in cash custody since/)).toBeInTheDocument();
    expect(evidence.getByText(/not assigned to the machine at that time/)).toBeInTheDocument();
    expect(
      evidence.getByText(/Reading 90 is lower than the machine's previous/),
    ).toBeInTheDocument();
    expect(evidence.getByText(/Tracking alert "Entered quarry B"/)).toBeInTheDocument();
    expect(
      evidence.getByText(/refused an attempt to approve an expense record/),
    ).toBeInTheDocument();
    expect(evidence.getByRole('link', { name: 'Open exceptions' })).toHaveAttribute(
      'href',
      `/tenant/exceptions?job_id=${JOB_ID}`,
    );
    expect(evidence.getByRole('link', { name: 'Open alerts' })).toHaveAttribute(
      'href',
      '/tenant/alerts',
    );
    expect(evidence.getByRole('link', { name: 'Open job J-1001' })).toHaveAttribute(
      'href',
      `/tenant/jobs/${JOB_ID}`,
    );
    expect(evidence.getByRole('button', { name: 'Open expense' })).toBeInTheDocument();
    expect(screen.getByText(/They are not a conclusion about any person/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/fraud/i);
  });

  it('assigns the case with the version read and an idempotency key', async () => {
    const user = userEvent.setup();
    mocks.assign.mockResolvedValue(makeDetail({ case: makeCase({ status: 'IN_REVIEW' }) }));
    renderDetail(ALL);
    await loaded();
    await user.click(screen.getByRole('button', { name: 'Assign' }));
    const dialog = within(await screen.findByRole('dialog'));
    await user.click(dialog.getByRole('combobox', { name: /Assignee/ }));
    await user.click(await screen.findByRole('option', { name: 'Rita Reviewer' }));
    await user.click(dialog.getByRole('button', { name: 'Assign' }));
    await waitFor(() => {
      expect(mocks.assign).toHaveBeenCalledWith(
        CASE_ID,
        { assignee_user_id: PERSON.user_id, version: 3 },
        expect.any(String),
      );
    });
    expect(mocks.search).toHaveBeenCalled();
    expect(await screen.findByText('Case assigned.')).toBeInTheDocument();
    expect(mocks.get).toHaveBeenCalledTimes(2);
  });

  it('shows the segregation-of-duties refusal when assigning someone in the evidence', async () => {
    const user = userEvent.setup();
    mocks.assign.mockRejectedValue(
      apiError(
        'SEGREGATION_OF_DUTIES',
        "This person's own records are part of the evidence; assign someone else",
      ),
    );
    renderDetail(ALL);
    await loaded();
    await user.click(screen.getByRole('button', { name: 'Assign' }));
    const dialog = within(await screen.findByRole('dialog'));
    await user.click(dialog.getByRole('combobox', { name: /Assignee/ }));
    await user.click(await screen.findByRole('option', { name: 'Rita Reviewer' }));
    await user.click(dialog.getByRole('button', { name: 'Assign' }));
    expect(
      await dialog.findByText(
        /SEGREGATION_OF_DUTIES: This person's own records are part of the evidence/,
      ),
    ).toBeInTheDocument();
    expect(dialog.getByText(/a colleague must do it/)).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('requires an outcome and an explanation of at least 10 characters to resolve', async () => {
    const user = userEvent.setup();
    renderDetail(ALL);
    await loaded();
    await user.click(screen.getByRole('button', { name: 'Resolve' }));
    const dialog = within(await screen.findByRole('dialog'));
    await user.click(dialog.getByRole('button', { name: 'Record outcome' }));
    expect(await dialog.findByText('Choose an outcome')).toBeInTheDocument();
    expect(dialog.getByText('An explanation is required')).toBeInTheDocument();
    await user.type(dialog.getByRole('textbox', { name: /Explanation/ }), 'too short');
    await user.click(dialog.getByRole('button', { name: 'Record outcome' }));
    expect(await dialog.findByText('At least 10 characters')).toBeInTheDocument();
    expect(mocks.resolve).not.toHaveBeenCalled();
  });

  it('resolves with outcome, explanation, version and an idempotency key', async () => {
    const user = userEvent.setup();
    mocks.resolve.mockResolvedValue(makeDetail({ case: makeCase({ status: 'RESOLVED' }) }));
    renderDetail(ALL);
    await loaded();
    await user.click(screen.getByRole('button', { name: 'Resolve' }));
    const dialog = within(await screen.findByRole('dialog'));
    await user.click(dialog.getByRole('combobox', { name: /Outcome/ }));
    await user.click(await screen.findByRole('option', { name: 'Legitimate explanation' }));
    await user.type(
      dialog.getByRole('textbox', { name: /Explanation/ }),
      'Night shift was approved by phone',
    );
    await user.click(dialog.getByRole('button', { name: 'Record outcome' }));
    await waitFor(() => {
      expect(mocks.resolve).toHaveBeenCalledWith(
        CASE_ID,
        {
          outcome: 'LEGITIMATE_EXPLANATION',
          explanation: 'Night shift was approved by phone',
          version: 3,
        },
        expect.stringMatching(/.{8,}/),
      );
    });
    expect(await screen.findByText('Outcome recorded.')).toBeInTheDocument();
  });

  it('shows the refusal when the reviewer is part of the evidence', async () => {
    const user = userEvent.setup();
    mocks.resolve.mockRejectedValue(
      apiError('SEGREGATION_OF_DUTIES', 'You cannot resolve a case built on your own records'),
    );
    renderDetail(ALL);
    await loaded();
    await user.click(screen.getByRole('button', { name: 'Resolve' }));
    const dialog = within(await screen.findByRole('dialog'));
    await user.click(dialog.getByRole('combobox', { name: /Outcome/ }));
    await user.click(await screen.findByRole('option', { name: 'Issue confirmed' }));
    await user.type(dialog.getByRole('textbox', { name: /Explanation/ }), 'Readings do not match');
    await user.click(dialog.getByRole('button', { name: 'Record outcome' }));
    expect(
      await dialog.findByText(
        /^SEGREGATION_OF_DUTIES: You cannot resolve a case built on your own/,
      ),
    ).toBeInTheDocument();
  });

  it('offers a reload when the case changed since it was read', async () => {
    const user = userEvent.setup();
    mocks.resolve.mockRejectedValue(
      new ApiError({ status: 409, code: 'STALE_VERSION', message: 'Changed', correlationId: null }),
    );
    renderDetail(ALL);
    await loaded();
    await user.click(screen.getByRole('button', { name: 'Resolve' }));
    const dialog = within(await screen.findByRole('dialog'));
    await user.click(dialog.getByRole('combobox', { name: /Outcome/ }));
    await user.click(await screen.findByRole('option', { name: 'Not confirmed' }));
    await user.type(
      dialog.getByRole('textbox', { name: /Explanation/ }),
      'Could not verify either way',
    );
    await user.click(dialog.getByRole('button', { name: 'Record outcome' }));
    await user.click(await dialog.findByRole('button', { name: 'Reload' }));
    await waitFor(() => {
      expect(mocks.get).toHaveBeenCalledTimes(2);
    });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('reopens a resolved case only with a reason of at least 10 characters', async () => {
    const user = userEvent.setup();
    mocks.get.mockResolvedValue(
      makeDetail({
        case: makeCase({
          status: 'RESOLVED',
          resolved_at: '2026-10-21T10:00:00Z',
          resolved_by: PERSON.user_id,
          latest_outcome: 'UNCONFIRMED',
        }),
        outcomes: [
          {
            id: 'o1',
            sequence: 1,
            outcome: 'UNCONFIRMED',
            explanation: 'No supporting records found',
            decided_by: PERSON.user_id,
            decided_by_name: 'Rita Reviewer',
            decided_at: '2026-10-21T10:00:00Z',
          },
        ],
      }),
    );
    mocks.reopen.mockResolvedValue(makeDetail());
    renderDetail(ALL);
    await loaded();
    const outcomes = within(screen.getByRole('list', { name: 'Case outcomes' }));
    expect(outcomes.getByText('No supporting records found')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Resolve' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Assign/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reopen' }));
    const dialog = within(await screen.findByRole('dialog'));
    await user.click(dialog.getByRole('button', { name: 'Reopen case' }));
    expect(await dialog.findByText('A reason is required')).toBeInTheDocument();
    await user.type(dialog.getByRole('textbox', { name: /Reason/ }), 'short');
    await user.click(dialog.getByRole('button', { name: 'Reopen case' }));
    expect(await dialog.findByText('At least 10 characters')).toBeInTheDocument();
    expect(mocks.reopen).not.toHaveBeenCalled();
    await user.type(
      dialog.getByRole('textbox', { name: /Reason/ }),
      ' — new fuel receipts arrived',
    );
    await user.click(dialog.getByRole('button', { name: 'Reopen case' }));
    await waitFor(() => {
      expect(mocks.reopen).toHaveBeenCalledWith(
        CASE_ID,
        { reason: 'short — new fuel receipts arrived', version: 3 },
        expect.any(String),
      );
    });
  });

  it('adds an append-only note', async () => {
    const user = userEvent.setup();
    mocks.addNote.mockResolvedValue({
      id: 'n1',
      kind: 'NOTE',
      body: 'Called the site supervisor',
      author_user_id: PERSON.user_id,
      author_name: 'Rita Reviewer',
      created_at: '2026-10-21T09:00:00Z',
    });
    renderDetail(ALL);
    await loaded();
    await user.type(
      screen.getByRole('textbox', { name: 'Add a note' }),
      'Called the site supervisor',
    );
    await user.click(screen.getByRole('button', { name: 'Add note' }));
    await waitFor(() => {
      expect(mocks.addNote).toHaveBeenCalledWith(
        CASE_ID,
        { body: 'Called the site supervisor' },
        expect.any(String),
      );
    });
    expect(await screen.findByText('Note added.')).toBeInTheDocument();
  });

  it('shows no commands to read-only tenants even with every case permission', async () => {
    renderDetail(ALL, 'READ_ONLY');
    await loaded();
    for (const name of ['Assign', 'Resolve', 'Reopen', 'Add note']) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument();
    }
    expect(screen.queryByRole('textbox', { name: 'Add a note' })).not.toBeInTheDocument();
  });

  it('shows only the commands the user is permitted to run', async () => {
    renderDetail(READ);
    await loaded();
    expect(screen.queryByRole('button', { name: 'Assign' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Resolve' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add note' })).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/fraud/i);
  });

  it('lets a manager without tenant.case.resolve assign but not resolve', async () => {
    renderDetail([...READ, P.tenantCaseManage]);
    await loaded();
    expect(screen.getByRole('button', { name: 'Assign' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Resolve' })).not.toBeInTheDocument();
  });
});
