import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Typography,
} from '@mui/material';
import { object, string, type ObjectSchema } from 'yup';
import { gatewayService } from '../../../api/services/platformCatalogService';
import type { GatewayCreatedDto, TelemetryAdapterKind } from '../../../api/types';
import { CopyButton } from '../../../components/display/CopyButton';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { ADAPTER_OPTIONS } from './trackerModelForm';

interface GatewayValues {
  name: string;
  adapter: TelemetryAdapterKind;
}

const gatewaySchema: ObjectSchema<GatewayValues> = object({
  name: string()
    .trim()
    .required('Name is required')
    .min(3, 'At least 3 characters')
    .max(100, 'At most 100 characters'),
  adapter: string<TelemetryAdapterKind>().oneOf(['TRACCAR']).required('Adapter is required'),
});

/** Register a telemetry gateway; the created key is handed to `onCreated`. Mount only while open. */
export function CreateGatewayDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (created: GatewayCreatedDto) => void;
}) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<GatewayValues>
      open
      title="Add telemetry gateway"
      initialValues={{ name: '', adapter: 'TRACCAR' }}
      validationSchema={gatewaySchema}
      submitLabel="Add gateway"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { name: v.name.trim(), adapter: v.adapter };
        onCreated(await gatewayService.create(body, keyFor(body)));
      }}
    >
      <FormikTextField name="name" label="Name" required />
      <FormikSelectField name="adapter" label="Adapter" options={ADAPTER_OPTIONS} />
    </FormDialog>
  );
}

export const GATEWAY_KEY_WARNING =
  'Copy this key now and store it in the gateway configuration. It is shown only once and cannot be retrieved later.';

/** One-time display of a new gateway's key. */
export function GatewayKeyDialog({
  created,
  onClose,
}: {
  created: GatewayCreatedDto;
  onClose: () => void;
}) {
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm" aria-labelledby="gateway-key-title">
      <DialogTitle id="gateway-key-title">Gateway {created.name} created</DialogTitle>
      <DialogContent dividers>
        <Alert severity="warning" className="mb-3">
          {GATEWAY_KEY_WARNING}
        </Alert>
        <Typography variant="caption" color="text.secondary">
          Gateway key
        </Typography>
        <Box className="mb-2 font-mono break-all" data-testid="gateway-key">
          {created.gateway_key}
        </Box>
        <CopyButton value={created.gateway_key} label="Copy key" />
      </DialogContent>
      <DialogActions>
        <Button variant="contained" onClick={onClose}>
          I have stored the key
        </Button>
      </DialogActions>
    </Dialog>
  );
}
