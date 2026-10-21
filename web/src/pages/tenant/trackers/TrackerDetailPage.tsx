import { useCallback, useState } from 'react';
import { useParams } from 'react-router';
import { trackerService } from '../../../api/services/trackerService';
import type { TrackerDto } from '../../../api/types';
import { AgeText } from '../../../components/display/AgeText';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { CapabilityMatrix } from '../../../components/fleet/CapabilityMatrix';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import {
  DetailSection,
  EntityDetailsLayout,
} from '../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNow } from '../../../hooks/useNow';
import { ROUTES } from '../../../navigation/routes';
import {
  CAPABILITY_LABELS,
  labelOf,
  TRACKER_STATE_OPTIONS,
  TRACKER_STATE_TONES,
} from '../shared/display';
import { IngestionEventsPanel } from './IngestionEventsPanel';
import { TrackerAssignmentSection } from './TrackerAssignmentSection';
import { useTrackerActions } from './useTrackerActions';

function DeviceFields({
  tracker,
  timeZone,
  now,
}: {
  tracker: TrackerDto;
  timeZone: string;
  now: number;
}) {
  return (
    <KeyValueGrid
      columns={3}
      items={[
        { label: 'Label', value: tracker.label },
        { label: 'External id', value: tracker.external_id },
        { label: 'Adapter', value: tracker.adapter },
        { label: 'Model id', value: tracker.tracker_model_id },
        { label: 'SIM ICCID', value: tracker.sim_iccid ?? '—' },
        { label: 'SIM MSISDN', value: tracker.sim_msisdn ?? '—' },
        { label: 'Carrier', value: tracker.carrier ?? '—' },
        {
          label: 'First report',
          value: <AgeText at={tracker.first_report_at} now={now} timeZone={timeZone} />,
        },
        {
          label: 'Last report',
          value: <AgeText at={tracker.last_report_at} now={now} timeZone={timeZone} />,
        },
      ]}
    />
  );
}

function TrackerEvents({ tracker, timeZone }: { tracker: TrackerDto; timeZone: string }) {
  const [status, setStatus] = useState('');
  return (
    <IngestionEventsPanel
      timeZone={timeZone}
      status={status}
      onStatusChange={setStatus}
      tracker={{ id: tracker.id, label: tracker.label }}
    />
  );
}

/** Tracker device record, assignment and history, capabilities, ingestion and lifecycle actions. */
export function TrackerDetailPage() {
  const { trackerId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const now = useNow();
  const load = useCallback(
    (signal: AbortSignal) => trackerService.get(trackerId, signal),
    [trackerId],
  );
  const resource = useAsyncResource(load);
  const tracker = resource.data;
  const { actionsFor, dialogs } = useTrackerActions({ timeZone, onChanged: resource.reload });

  return (
    <>
      <EntityDetailsLayout
        title={tracker === null ? 'Tracker' : `Tracker ${tracker.label}`}
        subtitle="Tracker details"
        back={{ label: 'All trackers', to: ROUTES.tenantTrackers }}
        {...(tracker !== null
          ? {
              status: (
                <StatusChip
                  status={tracker.provisioning_state}
                  tones={TRACKER_STATE_TONES}
                  label={labelOf(TRACKER_STATE_OPTIONS, tracker.provisioning_state)}
                />
              ),
              actions: <ActionButtons actions={actionsFor(tracker)} primaryKey="edit" />,
            }
          : {})}
        inactive={
          tracker?.provisioning_state === 'RETIRED'
            ? { title: 'This tracker is retired (decommissioned). Its history is kept read-only.' }
            : tracker?.provisioning_state === 'SUSPENDED'
              ? { title: 'This tracker is suspended: its data is quarantined until reactivated.' }
              : null
        }
      >
        <AsyncContent
          resource={resource}
          errorTitle="Could not load the tracker"
          loadingLabel="Loading tracker"
        >
          {(t) => (
            <div className="flex flex-col gap-6">
              <DetailSection title="Device">
                <DeviceFields tracker={t} timeZone={timeZone} now={now} />
              </DetailSection>
              <TrackerAssignmentSection tracker={t} timeZone={timeZone} />
              <DetailSection title="Capabilities">
                <CapabilityMatrix
                  capabilities={t.capabilities}
                  labels={CAPABILITY_LABELS}
                  timeZone={timeZone}
                  now={now}
                />
              </DetailSection>
              <DetailSection title="Ingestion events">
                <TrackerEvents tracker={t} timeZone={timeZone} />
              </DetailSection>
            </div>
          )}
        </AsyncContent>
      </EntityDetailsLayout>
      {dialogs}
    </>
  );
}
