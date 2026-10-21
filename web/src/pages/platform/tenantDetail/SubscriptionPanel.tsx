import { Button, Paper, Stack, Typography } from '@mui/material';
import { useState } from 'react';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { newIdempotencyKey } from '../../../api/ids';
import { subscriptionService } from '../../../api/services/subscriptionService';
import type { EntitlementDto, SubscriptionDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { humanize } from '../../../utils/text';
import { useNotify } from '../../../notifications/useNotify';
import { formatDate } from '../../../utils/dates';
import { CADENCE_OPTIONS, optionLabel, SUBSCRIPTION_TONES } from '../shared/billingDisplay';
import { allowedLifecycleActions } from './lifecycle';
import { TransitionDialog } from './TransitionDialog';

interface SubscriptionPanelProps {
  subscription: SubscriptionDto;
  onChanged: () => void;
}

function entitlementMessage(e: EntitlementDto): string {
  return `Subscription ${humanize(e.subscription_status).toLowerCase()}, access ${e.access_state}${
    e.changed ? ' (changed)' : ''
  }: ${e.reason}`;
}

export function SubscriptionPanel({ subscription: s, onChanged }: SubscriptionPanelProps) {
  const notify = useNotify();
  const [transitioning, setTransitioning] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const rate = s.current_rate;
  const canTransition = allowedLifecycleActions(s.status).length > 0;

  const evaluate = async () => {
    setEvaluating(true);
    try {
      // Each click is a separate intent: entitlement evaluation is deterministic and safe to repeat.
      const result = await subscriptionService.evaluateEntitlement(s.id, newIdempotencyKey());
      notify.info(entitlementMessage(result));
      onChanged();
    } catch (err) {
      notify.error(err);
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <Paper variant="outlined" className="p-4">
      <Stack direction="row" className="mb-3 flex-wrap items-center justify-between gap-2">
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <Typography variant="h6" component="h2">
            Subscription {s.agreement_number}
          </Typography>
          <StatusChip status={s.status} tones={SUBSCRIPTION_TONES} />
          {s.manually_suspended && (
            <StatusChip status="MANUALLY_SUSPENDED" tones={{ MANUALLY_SUSPENDED: 'error' }} />
          )}
        </Stack>
        <Can permission={PERMISSIONS.platformSubscriptionManage}>
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              loading={evaluating}
              onClick={() => {
                void evaluate();
              }}
            >
              Evaluate entitlement
            </Button>
            {canTransition && (
              <Button
                variant="contained"
                onClick={() => {
                  setTransitioning(true);
                }}
              >
                Change status
              </Button>
            )}
          </Stack>
        </Can>
      </Stack>
      <KeyValueGrid
        columns={4}
        items={[
          { label: 'Start date', value: formatDate(s.start_date) },
          {
            label: 'Billing start',
            value: `${formatDate(s.billing_start_date)} (anchor day ${String(s.billing_anchor_day)})`,
          },
          {
            label: 'Current period',
            value:
              s.current_period_start === null
                ? '—'
                : `${formatDate(s.current_period_start)} – ${formatDate(s.current_period_end)}`,
          },
          { label: 'Payment terms', value: `${String(s.payment_terms_days)} days` },
          { label: 'Enrolled assets', value: s.enrolled_assets },
          { label: 'Billable assets', value: s.billable_assets },
          {
            label: 'Current rate',
            value:
              rate === null ? (
                'No rate'
              ) : (
                <span>
                  <MoneyText amount={rate.unit_price} currency={rate.currency} /> per asset /{' '}
                  {optionLabel(CADENCE_OPTIONS, rate.cadence).toLowerCase()} (v{rate.version}, min{' '}
                  {rate.minimum_billable_assets})
                </span>
              ),
          },
          { label: 'Cancellation effective', value: formatDate(s.cancellation_effective_date) },
        ]}
      />
      {transitioning && (
        <TransitionDialog
          subscription={s}
          onClose={() => {
            setTransitioning(false);
          }}
          onTransitioned={(e) => {
            notify.success(entitlementMessage(e));
            onChanged();
          }}
        />
      )}
    </Paper>
  );
}
