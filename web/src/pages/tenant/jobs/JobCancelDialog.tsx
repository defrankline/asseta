import { jobService } from '../../../api/services/jobService';
import type { JobDto } from '../../../api/types';
import { DeactivateDialog } from '../../../components/lifecycle/DeactivateDialog';
import { cancelLabelFor, JOB_ERROR_HINTS } from '../shared/jobDisplay';

interface JobCancelDialogProps {
  job: JobDto;
  onClose: () => void;
  onDone: (job: JobDto) => void;
  onReload: () => void;
}

/** Cancel a job (`CANCEL` transition) with a required reason recorded in the audit trail. */
export function JobCancelDialog({ job, onClose, onDone, onReload }: JobCancelDialogProps) {
  const label = cancelLabelFor(job);
  const decline = label !== 'Cancel job';
  return (
    <DeactivateDialog<JobDto>
      entityLabel={job.job_number}
      noun="job"
      title={`${label} ${job.job_number}`}
      confirmLabel={label}
      description={
        decline ? (
          <p className="m-0">
            The field request <strong>{job.job_number}</strong>
            {` from ${job.requested_by_name ?? 'a supervisor'} `}
            will be declined. The supervisor is told your reason; the request stays on record as a
            cancelled job.
          </p>
        ) : (
          <p className="m-0">
            Job <strong>{job.job_number}</strong> will be cancelled and its machine released. The
            job, its price snapshot and any readings stay on record; a cancelled job cannot be
            restarted.
          </p>
        )
      }
      errorHints={JOB_ERROR_HINTS}
      onConfirm={(reason, key) => jobService.transition(job.id, { action: 'CANCEL', reason }, key)}
      onDone={onDone}
      onClose={onClose}
      onReload={onReload}
    />
  );
}
