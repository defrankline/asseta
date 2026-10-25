import { useParams } from 'react-router';
import { engineHoursService } from '../../../api/services/engineHoursService';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { ROUTES } from '../../../navigation/routes';
import { RecordDetail } from '../shared/RecordDetail';
import { useRecordById } from '../shared/useRecordById';
import { hoursText } from './engineHoursDisplay';
import {
  engineHoursLink,
  machineOf,
  proposalChip,
  useBaselineKit,
  useClassificationKit,
  useCorrectionKit,
} from './engineRecords';

const loadBaseline = (id: string, signal: AbortSignal) =>
  engineHoursService.getBaseline(id, signal);
const loadCorrection = (id: string, signal: AbortSignal) =>
  engineHoursService.getCorrection(id, signal);
const loadClassification = (id: string, signal: AbortSignal) =>
  engineHoursService.getClassification(id, signal);

/** One meter baseline proposal (exact-record link): details, decide, history. */
export function MeterBaselineDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(loadBaseline, id);
  const kit = useBaselineKit(res.reload);
  return (
    <>
      <RecordDetail
        resource={res}
        what="meter baseline"
        back={{ label: 'Meter baselines', to: ROUTES.tenantMeterBaselines }}
        timeZone={timeZone}
        title={(b) => `Baseline · ${machineOf(b)}`}
        status={proposalChip}
        actions={kit.actionsFor}
        primaryKey="decide"
        links={engineHoursLink}
        items={kit.items}
        history={kit.history}
      />
      {kit.dialog}
    </>
  );
}

/** One reading correction proposal (exact-record link): details, decide, history. */
export function MeterCorrectionDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(loadCorrection, id);
  const kit = useCorrectionKit(res.reload);
  return (
    <>
      <RecordDetail
        resource={res}
        what="reading correction"
        back={{ label: 'Reading corrections', to: ROUTES.tenantMeterCorrections }}
        timeZone={timeZone}
        title={(c) => `Correction · ${machineOf(c)}`}
        status={proposalChip}
        actions={kit.actionsFor}
        primaryKey="decide"
        links={engineHoursLink}
        items={kit.items}
        history={kit.history}
      />
      {kit.dialog}
    </>
  );
}

/** One explanation of unallocated engine hours (exact-record link): details, decide, history. */
export function ClassificationDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(loadClassification, id);
  const kit = useClassificationKit(res.reload);
  return (
    <>
      <RecordDetail
        resource={res}
        what="hour explanation"
        back={{ label: 'Hour explanations', to: ROUTES.tenantEngineHourClassifications }}
        timeZone={timeZone}
        title={(c) => `Explanation · ${hoursText(c.hours)} · ${machineOf(c)}`}
        status={proposalChip}
        actions={kit.actionsFor}
        primaryKey="decide"
        links={engineHoursLink}
        items={kit.items}
        history={kit.history}
      />
      {kit.dialog}
    </>
  );
}
