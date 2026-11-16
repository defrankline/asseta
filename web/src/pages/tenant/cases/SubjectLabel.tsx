import type { SubjectType } from '../../../api/types';
import { shortId } from '../shared/financeDisplay';
import { PersonName } from '../shared/PersonName';
import { SUBJECT_TYPE_LABELS } from './caseDisplay';

interface SubjectLabelProps {
  subjectType: SubjectType;
  subjectId: string;
  machineName: (id: string) => string;
  staffName: (id: string | null) => string;
}

/** What a case or signal is about, resolved to a readable label (machine, staff, expense, person). */
export function SubjectLabel({
  subjectType,
  subjectId,
  machineName,
  staffName,
}: SubjectLabelProps) {
  const kind = SUBJECT_TYPE_LABELS[subjectType];
  switch (subjectType) {
    case 'MACHINE':
      return <>{machineName(subjectId)}</>;
    case 'STAFF':
      return <>{staffName(subjectId)}</>;
    case 'EXPENSE':
      return <>{`${kind} ${shortId(subjectId)}`}</>;
    case 'USER':
      return <PersonName userId={subjectId} />;
  }
}
