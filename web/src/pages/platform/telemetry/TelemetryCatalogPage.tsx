import { Box, Paper, Tab, Tabs } from '@mui/material';
import { useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useSession } from '../../../session/useSession';
import { GatewaysTab } from './GatewaysTab';
import { TrackerModelsTab } from './TrackerModelsTab';

type TabKey = 'models' | 'gateways';

/** Platform telemetry catalog: approved tracker models and telemetry gateways. */
export function TelemetryCatalogPage() {
  const { hasPermission } = useSession();
  const available: { key: TabKey; label: string }[] = [
    ...(hasPermission(PERMISSIONS.platformTrackerModelRead)
      ? [{ key: 'models' as const, label: 'Tracker models' }]
      : []),
    ...(hasPermission(PERMISSIONS.platformGatewayRead)
      ? [{ key: 'gateways' as const, label: 'Gateways' }]
      : []),
  ];
  const [tab, setTab] = useState<TabKey | null>(null);
  const active = available.find((t) => t.key === tab)?.key ?? available[0]?.key ?? null;
  return (
    <>
      <PageHeader
        title="Trackers & gateways"
        subtitle="Approved tracker models offered to tenants, and the gateways that push telemetry"
      />
      {active !== null && (
        <Paper variant="outlined">
          <Tabs
            value={active}
            onChange={(_e, v: TabKey) => {
              setTab(v);
            }}
            aria-label="Telemetry catalog"
          >
            {available.map((t) => (
              <Tab key={t.key} value={t.key} label={t.label} />
            ))}
          </Tabs>
          <Box className="p-3">
            {active === 'models' && <TrackerModelsTab />}
            {active === 'gateways' && <GatewaysTab />}
          </Box>
        </Paper>
      )}
    </>
  );
}
