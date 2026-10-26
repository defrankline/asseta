import type { CashHandoverDto } from '../../../../api/types';
import { nameOr } from '../../shared/names';
import {
  NO_REMITTANCE_REQUIREMENTS,
  REMITTANCE_METHOD_LABELS,
  type RemittanceRequirements,
} from './cashForms';
import { useCashPolicy } from './custodyHooks';

/**
 * What the tenant's CASH_CUSTODY policy requires of a remittance. Readable with the policy or the
 * recording permission (as the field apps); otherwise nothing is enforced here and the server's
 * refusal explains it.
 */
export function useRemittanceRequirements(): RemittanceRequirements {
  return useCashPolicy()?.remittance ?? NO_REMITTANCE_REQUIREMENTS;
}

/** Plain-language list of the switched-on requirements (empty when none apply). */
export function requirementLines(req: RemittanceRequirements): string[] {
  const lines: string[] = [];
  if (req.account) lines.push('the company account the money was paid into');
  if (req.reference) lines.push('the transaction reference for bank and mobile-money remittances');
  if (req.evidence) lines.push('a photo of the deposit slip or payment confirmation');
  return lines;
}

/** No method recorded = cash to the office (as before remittance details existed). */
export const remittanceMethodText = (h: CashHandoverDto) =>
  REMITTANCE_METHOD_LABELS[h.method ?? 'CASH_TO_OFFICE'];

export const remittanceAccountText = (h: CashHandoverDto) =>
  h.deposit_account_id == null ? '—' : nameOr(h.deposit_account_name, h.deposit_account_id);
