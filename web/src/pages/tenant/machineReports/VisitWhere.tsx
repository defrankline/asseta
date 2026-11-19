import { Link, Typography } from '@mui/material';
import { whereParts, type VisitPlace } from './visitDisplay';

/**
 * Inline "Where: {place} (at {site}) · {lat}, {lng} (±{acc} m)"; the coordinates open OpenStreetMap
 * in a new tab. Nothing without coordinates.
 */
export function WhereText({ place }: { place: VisitPlace }) {
  const w = whereParts(place);
  if (w === null) return null;
  return (
    <>
      Where: {w.label === '' ? '' : `${w.label} · `}
      <Link href={w.mapUrl} target="_blank" rel="noopener noreferrer">
        {w.coords}
      </Link>
      {w.accuracy}
    </>
  );
}

/** The Where line on its own row (nothing without coordinates). */
export function VisitWhere({ place }: { place: VisitPlace }) {
  if (whereParts(place) === null) return null;
  return (
    <Typography variant="body2" color="text.secondary">
      <WhereText place={place} />
    </Typography>
  );
}
