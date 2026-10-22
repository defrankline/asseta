import { Alert, Box, Button, Divider, Tab, Tabs } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../access/permissionCodes';
import { toApiError } from '../../api/ApiError';
import type { NotificationPreferenceDto } from '../../api/types';
import { AsyncContent } from '../../components/feedback/AsyncContent';
import { PageHeader } from '../../components/feedback/PageHeader';
import { useAsyncResource } from '../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../hooks/useIdempotencyKey';
import { ROUTES } from '../../navigation/routes';
import { useNotificationCenter } from '../../notifications/center/NotificationCenterContext';
import { useNotify } from '../../notifications/useNotify';
import { useSession } from '../../session/useSession';
import { effective, preferenceChanges, type Channel, type Draft } from './preferences';
import { PreferencesTable } from './PreferencesTable';
import { PushDevicesSection } from './PushDevicesSection';
import { RoutingEditor } from './RoutingEditor';
import { SmsProfileSection } from './SmsProfileSection';

function PreferencesEditor({ tenantDefault }: { tenantDefault: boolean }) {
  const notify = useNotify();
  const { service } = useNotificationCenter();
  const load = useCallback(
    (signal: AbortSignal) => service.getPreferences(tenantDefault, signal),
    [service, tenantDefault],
  );
  const prefs = useAsyncResource(load);
  const [draft, setDraft] = useState<Draft>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const keyFor = useIdempotencyKey();
  const changes = preferenceChanges(prefs.data ?? [], draft);

  const toggle = (p: NotificationPreferenceDto, channel: Channel, value: boolean) => {
    setDraft((d) => ({ ...d, [p.type]: { ...effective(p, d), [channel]: value } }));
  };

  const save = () => {
    const body = { changes, tenant_default: tenantDefault };
    setSaving(true);
    setSaveError(null);
    service
      .updatePreferences(body, keyFor(body))
      .then(() => {
        notify.success(
          tenantDefault ? 'Tenant defaults saved.' : 'Notification preferences saved.',
        );
        setDraft({});
        prefs.reload();
      })
      .catch((err: unknown) => {
        const e = toApiError(err);
        setSaveError(e.code === 'MANDATORY_CHANNEL' ? `${e.message} (${e.code})` : e.message);
      })
      .finally(() => {
        setSaving(false);
      });
  };

  return (
    <AsyncContent
      resource={prefs}
      isEmpty={(rows) => rows.length === 0}
      emptyTitle="No notification types"
      errorTitle="Could not load notification preferences"
    >
      {(rows) => (
        <Box className="flex flex-col gap-4">
          {tenantDefault && (
            <Alert severity="info">
              Defaults for everyone in this tenant. A user&apos;s own choices take precedence;
              required channels cannot be switched off.
            </Alert>
          )}
          <PreferencesTable prefs={rows} draft={draft} onToggle={toggle} />
          {saveError !== null && <Alert severity="error">{saveError}</Alert>}
          <Box className="flex justify-end gap-2">
            <Button
              disabled={changes.length === 0 || saving}
              onClick={() => {
                setDraft({});
              }}
            >
              Discard changes
            </Button>
            <Button
              variant="contained"
              disabled={changes.length === 0}
              loading={saving}
              onClick={save}
            >
              {tenantDefault ? 'Save tenant defaults' : 'Save preferences'}
            </Button>
          </Box>
        </Box>
      )}
    </AsyncContent>
  );
}

/**
 * Per notification type: in-app and SMS delivery for the signed-in user (and, for tenant owners
 * with `tenant.notification.manage`, the tenant-wide defaults); mandatory channels locked.
 */
export function NotificationPreferencesPage() {
  const { mode, hasPermission } = useSession();
  const canDefaults = mode.kind === 'tenant' && hasPermission(PERMISSIONS.tenantNotificationManage);
  const [tab, setTab] = useState<'mine' | 'tenant'>('mine');
  const tenantDefault = canDefaults && tab === 'tenant';
  return (
    <>
      <PageHeader
        title="Notification preferences"
        subtitle="Choose how you are told about each kind of event in this console: in-app, SMS, push and e-mail"
        actions={
          <Button component={RouterLink} to={ROUTES.notifications}>
            Back to notifications
          </Button>
        }
      />
      <Box className="flex flex-col gap-4">
        <SmsProfileSection />
        {canDefaults && (
          <Tabs
            value={tab}
            onChange={(_e, v: 'mine' | 'tenant') => {
              setTab(v);
            }}
            aria-label="Preference scope"
          >
            <Tab value="mine" label="My preferences" />
            <Tab value="tenant" label="Tenant defaults" />
          </Tabs>
        )}
        <PreferencesEditor key={tenantDefault ? 'tenant' : 'mine'} tenantDefault={tenantDefault} />
        <Divider />
        <RoutingEditor
          key={tenantDefault ? 'routing-tenant' : 'routing-mine'}
          console={mode.kind === 'tenant' ? 'tenant' : 'platform'}
          tenantDefault={tenantDefault}
        />
        {!tenantDefault && (
          <>
            <Divider />
            <PushDevicesSection />
          </>
        )}
      </Box>
    </>
  );
}
