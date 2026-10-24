/** Signature drawing surface size in canvas pixels (CSS scales it to the dialog width). */
export const PAD_WIDTH = 600;
export const PAD_HEIGHT = 200;

/** Pointer position in canvas pixels for a canvas drawn at `rect` on screen. */
export function canvasPoint(
  clientX: number,
  clientY: number,
  rect: { left: number; top: number; width: number; height: number },
  width = PAD_WIDTH,
  height = PAD_HEIGHT,
): { x: number; y: number } {
  const sx = rect.width > 0 ? width / rect.width : 1;
  const sy = rect.height > 0 ? height / rect.height : 1;
  return { x: (clientX - rect.left) * sx, y: (clientY - rect.top) * sy };
}
