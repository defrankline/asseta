import { Button, Paper, Stack, Typography } from '@mui/material';
import { useState } from 'react';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type { TenantDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstant } from '../../../utils/dates';
import { ACCESS_TONES, TENANT_STATUS_TONES, VERIFICATION_TONES } from '../shared/billingDisplay';
import { VerifyTenantDialog } from './VerifyTenantDialog';

interface CompanyPanelProps {
  tenant: TenantDto;
  onChanged: () => void;
}

export function CompanyPanel({ tenant: t, onChanged }: CompanyPanelProps) {
  const notify = useNotify();
  const [verifying, setVerifying] = useState(false);
  return (
    <Paper variant="outlined" className="p-4">
      <Stack direction="row" className="mb-3 flex-wrap items-center justify-between gap-2">
        <Typography variant="h6" component="h2">
          Company
        </Typography>
        <Can permission={PERMISSIONS.platformTenantVerify}>
          <Button
            variant="outlined"
            onClick={() => {
              setVerifying(true);
            }}
          >
            Verify company
          </Button>
        </Can>
      </Stack>
      <KeyValueGrid
        items={[
          { label: 'Legal name', value: t.legal_name },
          { label: 'Display name', value: t.display_name },
          { label: 'Registration no.', value: t.registration_number ?? '—' },
          { label: 'Contact', value: t.contact_name },
          { label: 'Contact email', value: t.contact_email },
          { label: 'Contact phone', value: t.contact_phone ?? '—' },
          {
            label: 'Tenant status',
            value: <StatusChip status={t.status} tones={TENANT_STATUS_TONES} />,
          },
          {
            label: 'Verification',
            value: <StatusChip status={t.verification_status} tones={VERIFICATION_TONES} />,
          },
          {
            label: 'Access',
            value: (
              <span>
                <StatusChip status={t.access_state} tones={ACCESS_TONES} />{' '}
                {t.access_state_reason ?? ''}
              </span>
            ),
          },
          { label: 'Created', value: formatInstant(t.created_at) },
        ]}
      />
      {verifying && (
        <VerifyTenantDialog
          tenant={t}
          onClose={() => {
            setVerifying(false);
          }}
          onVerified={(next) => {
            notify.success(`Verification set to ${next.verification_status.toLowerCase()}.`);
            onChanged();
          }}
        />
      )}
    </Paper>
  );
}
