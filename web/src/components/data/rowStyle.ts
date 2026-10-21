/** Table row classes: pointer when clickable; inactive records muted (still readable). */
export function rowClassName(clickable: boolean, muted: boolean): string | undefined {
  const classes = [clickable ? 'cursor-pointer' : '', muted ? 'opacity-60' : ''].filter(
    (c) => c !== '',
  );
  return classes.length === 0 ? undefined : classes.join(' ');
}
