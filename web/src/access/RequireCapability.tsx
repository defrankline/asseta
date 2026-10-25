import BlockOutlined from '@mui/icons-material/BlockOutlined';
import { Button } from '@mui/material';
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { EmptyState } from '../components/feedback/EmptyState';
import { useCapabilityEnabled, type CapabilityCode } from './capabilities';

/** The plain state shown instead of a page whose capability the tenant has switched off. */
export function CapabilityOffState({ feature }: { feature: string }) {
  return (
    <EmptyState
      icon={<BlockOutlined fontSize="large" />}
      title={`${feature} is not enabled for your company`}
      description="Your company's settings switch this feature off. An administrator can switch it on in Policies."
      action={
        <Button component={Link} to="/" variant="outlined">
          Go home
        </Button>
      }
    />
  );
}

interface RequireCapabilityProps {
  capability: CapabilityCode;
  /** Feature name in the "not enabled" message, e.g. "Customer hours". */
  feature: string;
  children: ReactNode;
}

/** Renders `children` only while the capability is on (direct URLs included). */
export function RequireCapability({ capability, feature, children }: RequireCapabilityProps) {
  return useCapabilityEnabled(capability) ? (
    <>{children}</>
  ) : (
    <CapabilityOffState feature={feature} />
  );
}
