import type { QueryParams } from '../../api/client';
import type { ReportDefinitionDto } from '../../api/types';

/** One report the page can export, with the page's current list filters (query-parameter names). */
export interface ExportRequest {
  code: string;
  filters?: Readonly<Record<string, string | null | undefined>>;
}

/** Only the filters the report accepts (the API rejects unknown parameters), without empty values. */
export function exportParams(
  definition: Pick<ReportDefinitionDto, 'filters'>,
  filters: ExportRequest['filters'],
): QueryParams {
  const params: QueryParams = {};
  for (const name of definition.filters) {
    const value = filters?.[name];
    if (value !== undefined && value !== null && value !== '') params[name] = value;
  }
  return params;
}

/** Hands a downloaded file to the browser through a temporary object URL. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = 'noopener';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 0);
}
