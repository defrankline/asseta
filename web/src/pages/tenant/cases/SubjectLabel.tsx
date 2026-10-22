import { useCallback } from 'react';
import { jobService } from '../../../api/services/jobService';
import type { SubjectType } from '../../../api/types';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { shortId } from '../shared/financeDisplay';
import { PersonName } from '../shared/PersonName';
import { SUBJECT_TYPE_LABELS } from './caseDisplay';

/** Job number for a job id (the short id until loaded or when the job cannot be read). */
export function JobNumber({ jobId }: { jobId: string }) {
  const load = useCallback(
    async (signal: AbortSignal) => (await jobService.summary(jobId, signal)).job.job_number,
    [jobId],
  );
  const res = useAsyncResource(load);
  return <>{res.data ?? shortId(jobId)}</>;
}

interface SubjectLabelProps {
  subjectType: SubjectType;
  subjectId: string;
  machineName: (id: string) => string;
  staffName: (id: string | null) => string;
}

/** What a case or signal is about, resolved to a readable label (machine, job, staff, expense, person). */
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
    case 'JOB':
      return (
        <>
          {kind} <JobNumber jobId={subjectId} />
        </>
      );
    case 'STAFF':
      return <>{staffName(subjectId)}</>;
    case 'EXPENSE':
      return <>{`${kind} ${shortId(subjectId)}`}</>;
    case 'USER':
      return <PersonName userId={subjectId} />;
  }
}
