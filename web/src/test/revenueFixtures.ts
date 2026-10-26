import type {
  DailyMachineSheetDetailDto,
  DailyMachineSheetRowDto,
  NonRevenueActivityDto,
  NonRevenueApprovalDto,
  Page,
  RevenueDifferenceDto,
  RevenueReasonDto,
} from '../api/types';
import { JOB_ID, MACHINE_ID, ME_ID } from './jobFixtures';

export const OTHER_ID = '44444444-4444-4444-8444-444444444444';
export const DIFFERENCE_ID = 'ffffffff-0000-4000-8000-000000000001';
export const APPROVAL_ID = 'ffffffff-0000-4000-8000-000000000002';
export const ACTIVITY_ID = 'ffffffff-0000-4000-8000-000000000003';
export const INVOICE_ID = 'ffffffff-0000-4000-8000-000000000004';
export const PURCHASE_ID = 'ffffffff-0000-4000-8000-000000000005';
export const CASE_ID = 'ffffffff-0000-4000-8000-000000000006';

export const page = <T>(items: T[]): Page<T> => ({
  items,
  total: items.length,
  page: 1,
  page_size: 25,
});

export const REVENUE_REASON: RevenueReasonDto = {
  id: 'ffffffff-0000-4000-8000-0000000000aa',
  code: 'MOVE',
  name: 'Movement between sites',
  description: null,
  is_active: true,
  version: 1,
};

export function makeDifference(over: Partial<RevenueDifferenceDto> = {}): RevenueDifferenceDto {
  return {
    id: DIFFERENCE_ID,
    machine_id: MACHINE_ID,
    machine_code: 'EX-01',
    machine_name: 'Excavator',
    period_kind: 'DAY',
    period_key: '2026-10-20',
    period_start: '2026-10-19T21:00:00Z',
    period_end: '2026-10-20T21:00:00Z',
    local_from: '2026-10-20',
    local_to: '2026-10-20',
    job_id: null,
    job_number: null,
    currency: 'TZS',
    expected_amount: '500000.0000',
    in_progress_amount: '0.0000',
    attributed_amount: '300000.0000',
    difference: '200000.0000',
    customer_work_hours: '8.00',
    non_revenue_hours: '0.00',
    unexplained_hours: '1.00',
    unexplained_expected_amount: '50000.0000',
    detail: {
      jobs: [
        {
          job_id: JOB_ID,
          job_number: 'J-100',
          currency: 'TZS',
          expected: '450000.0000',
          in_progress: '0.0000',
          attributed: '300000.0000',
          completed: true,
        },
      ],
      money_sources: [
        {
          source: 'INVOICE_LINE',
          ref_id: 'ffffffff-0000-4000-8000-0000000000b1',
          parent_id: INVOICE_ID,
          job_id: JOB_ID,
          currency: 'TZS',
          amount: '300000.0000',
          hours: null,
        },
      ],
    },
    status: 'OPEN',
    case_id: null,
    case_number: null,
    policy_version: 'RR:T1',
    opened_at: '2026-10-21T03:00:00Z',
    computed_at: '2026-10-21T03:00:00Z',
    reason_id: null,
    reason_name: null,
    explanation_note: null,
    explained_by: null,
    explained_at: null,
    decided_by: null,
    decided_at: null,
    decision_note: null,
    adjustments: [],
    adjusted_difference: null,
    ...over,
  };
}

export function makeActivity(over: Partial<NonRevenueActivityDto> = {}): NonRevenueActivityDto {
  return {
    activity_id: ACTIVITY_ID,
    job_id: JOB_ID,
    job_number: 'J-100',
    machine_id: MACHINE_ID,
    machine_code: 'EX-01',
    machine_name: 'Excavator',
    activity_type: 'MOBILIZATION',
    started_at: '2026-10-20T05:00:00Z',
    ended_at: '2026-10-20T06:30:00Z',
    hours: '1.50',
    note: 'Drove to site B',
    approval_id: null,
    approval_status: 'NONE',
    ...over,
  };
}

export function makeApproval(over: Partial<NonRevenueApprovalDto> = {}): NonRevenueApprovalDto {
  return {
    id: APPROVAL_ID,
    activity_id: ACTIVITY_ID,
    job_id: JOB_ID,
    job_number: 'J-100',
    machine_id: MACHINE_ID,
    machine_code: 'EX-01',
    machine_name: 'Excavator',
    activity_type: 'MOBILIZATION',
    started_at: '2026-10-20T05:00:00Z',
    ended_at: '2026-10-20T06:30:00Z',
    hours: '1.50',
    reason_id: REVENUE_REASON.id,
    reason_name: REVENUE_REASON.name,
    note: 'Drove to site B',
    status: 'PROPOSED',
    proposed_by: ME_ID,
    proposed_by_name: 'Me',
    proposed_at: '2026-10-20T07:00:00Z',
    decided_by: null,
    decided_by_name: null,
    decided_at: null,
    decision_note: null,
    policy_version: 'RR:T1',
    ...over,
  };
}

export function makeSheetRow(over: Partial<DailyMachineSheetRowDto> = {}): DailyMachineSheetRowDto {
  return {
    machine_id: MACHINE_ID,
    machine_code: 'EX-01',
    machine_name: 'Excavator',
    day: '2026-10-20',
    first_reading: '1000.0',
    last_reading: '1010.0',
    reading_count: 2,
    engine_hours: '10.00',
    customer_work_hours: '8.00',
    non_revenue_hours: '1.00',
    non_revenue_by_type: { MOBILIZATION: '1.00' },
    non_revenue_pending_hours: '0.50',
    revenue_hours: '7.50',
    approved_non_customer_hours: '0.00',
    identified_variance_hours: '0.00',
    unexplained_hours: '1.00',
    pending_review_hours: '0.00',
    fuel_litres: '120.0',
    fuel_litres_per_engine_hour: '12.00',
    jobs: [
      {
        job_id: JOB_ID,
        job_number: 'J-100',
        billing_mode: 'INVOICE',
        status: 'COMPLETED',
        customer_id: null,
        customer_name: 'Acme Ltd',
        job_site_id: null,
        job_site_name: 'Site B',
        customer_work_hours: '8.00',
        revenue_hours: '7.50',
      },
    ],
    money: [
      {
        currency: 'TZS',
        expected: '500000.0000',
        in_progress: '0.0000',
        attributed: '300000.0000',
        difference: '200000.0000',
        unexplained_hours: '1.00',
        unexplained_expected: '50000.0000',
      },
      {
        currency: 'USD',
        expected: '100.0000',
        in_progress: '0.0000',
        attributed: '100.0000',
        difference: '0.0000',
        unexplained_hours: '0.00',
        unexplained_expected: '0.0000',
      },
    ],
    flags: ['REVENUE_DIFFERENCE', 'UNEXPLAINED_HOURS'],
    ...over,
  };
}

export function makeSheetDay(
  over: Partial<DailyMachineSheetDetailDto> = {},
): DailyMachineSheetDetailDto {
  return {
    ...makeSheetRow(),
    readings: [
      {
        id: 'ffffffff-0000-4000-8000-0000000000c1',
        kind: 'OPENING',
        captured_at: '2026-10-20T04:00:00Z',
        reading: '1000.0',
        state: 'ACCEPTED',
        job_id: JOB_ID,
        job_number: 'J-100',
      },
    ],
    segments: [
      {
        start_ref: 'a',
        end_ref: 'b',
        start_at: '2026-10-20T04:00:00Z',
        end_at: '2026-10-20T14:00:00Z',
        kind: 'CUSTOMER_WORK',
        classification: 'NOT_APPLICABLE',
        review: 'VERIFIED',
        hours_in_day: '9.00',
        customer_work_hours_in_day: '8.00',
        non_revenue_by_type: { MOBILIZATION: '1.00' },
        job_id: JOB_ID,
        job_number: 'J-100',
      },
    ],
    money_sources: [
      {
        source: 'INVOICE_LINE',
        ref_id: 'ffffffff-0000-4000-8000-0000000000b1',
        parent_id: INVOICE_ID,
        job_id: JOB_ID,
        job_number: 'J-100',
        currency: 'TZS',
        amount: '300000.0000',
        hours: null,
      },
      {
        source: 'PREPAID_CONSUMPTION',
        ref_id: 'ffffffff-0000-4000-8000-0000000000b2',
        parent_id: PURCHASE_ID,
        job_id: JOB_ID,
        job_number: 'J-100',
        currency: 'USD',
        amount: '100.0000',
        hours: '2.00',
      },
    ],
    flag_records: [
      { flag: 'REVENUE_DIFFERENCE', record_type: 'revenue_difference', record_id: DIFFERENCE_ID },
    ],
    fuel_events: [
      {
        id: 'ffffffff-0000-4000-8000-0000000000d1',
        event_type: 'ISSUE',
        litres: '120.0',
        occurred_at: '2026-10-20T05:00:00Z',
        job_id: JOB_ID,
      },
    ],
    ...over,
  };
}
