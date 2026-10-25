import { PERMISSIONS } from '../../../access/permissionCodes';
import type { CreditArrangementDto } from '../../../api/hoursTypes';
import { creditArrangementService } from '../../../api/services/hoursService';
import { MoneyText } from '../../../components/display/MoneyText';
import { CreditFormDialog } from './proposalForms';
import type { ProposalConfig } from './proposalKit';
import { ProposalDetailPage, ProposalsPage } from './ProposalsPage';
import { useHoursPolicy } from './useHoursPolicy';

/** Credit arrangement proposals as the list and detail pages need them. */
function useCreditConfig(): ProposalConfig<CreditArrangementDto> {
  const hours = useHoursPolicy();
  return {
    kind: 'HOURS_CREDIT',
    title: 'Credit arrangements',
    subtitle: 'How much prepaid hours a customer may use before paying, within approved limits',
    noun: 'credit arrangement',
    calls: creditArrangementService,
    proposePermission: PERMISSIONS.tenantHoursCredit,
    approvePermission: PERMISSIONS.tenantHoursCreditApprove,
    allowed: (p) => p.creditAllowed,
    valueColumns: [
      {
        id: 'limit',
        header: 'Limit',
        align: 'right',
        render: (c) => <MoneyText amount={c.limit_amount} currency={c.currency} />,
      },
    ],
    valueItems: (c) => [
      { label: 'Limit', value: <MoneyText amount={c.limit_amount} currency={c.currency} /> },
      { label: 'Terms', value: c.terms ?? '—' },
    ],
    approveExplanation:
      'Once approved, hours may be activated on credit for this customer up to the available limit.',
    renderForm: (props) => (
      <CreditFormDialog {...props} reasonCodeRequired={hours.policy?.reasonCodeRequired ?? false} />
    ),
  };
}

/** Customer credit arrangements: proposed by one person, approved by another; limit the credit activations. */
export function CreditArrangementsPage() {
  return <ProposalsPage<CreditArrangementDto> {...useCreditConfig()} />;
}

/** One credit arrangement (exact-record link). */
export function CreditArrangementDetailPage() {
  return <ProposalDetailPage<CreditArrangementDto> {...useCreditConfig()} />;
}
