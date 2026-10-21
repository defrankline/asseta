import { jobService } from '../../../api/services/jobService';
import type { JobDto } from '../../../api/types';
import { DeactivateDialog } from '../../../components/lifecycle/DeactivateDialog';
import { JOB_ERROR_HINTS } from '../shared/jobDisplay';

interface JobCancelDialogProps {
  job: JobDto;
  onClose: () => void;
  onDone: (job: JobDto) => void;
  onReload: () => void;
}

/** Cancel a job (`CANCEL` transition) with a required reason recorded in the audit trail. */
export function JobCancelDialog({ job, onClose, onDone, onReload }: JobCancelDialogProps) {
  return (
    <DeactivateDialog<JobDto>
      entityLabel={job.job_number}
      noun="job"
      title={`Cancel job ${job.job_number}`}
      confirmLabel="Cancel job"
      description={
        <p className="m-0">
          Job <strong>{job.job_number}</strong> will be cancelled and its machine released. The job,
          its price snapshot and any readings stay on record; a cancelled job cannot be restarted.
        </p>
      }
      errorHints={JOB_ERROR_HINTS}
      onConfirm={(reason, key) => jobService.transition(job.id, { action: 'CANCEL', reason }, key)}
      onDone={onDone}
      onClose={onClose}
      onReload={onReload}
    />
  );
}
