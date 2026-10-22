import KeyboardArrowDown from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowRight from '@mui/icons-material/KeyboardArrowRight';
import SearchIcon from '@mui/icons-material/Search';
import {
  Box,
  Collapse,
  IconButton,
  InputAdornment,
  LinearProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
  TextField,
} from '@mui/material';
import { Fragment, useEffect, useState, type KeyboardEvent, type ReactNode } from 'react';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { EmptyState } from '../feedback/EmptyState';
import { ErrorState } from '../feedback/ErrorState';
import { LoadingState } from '../feedback/LoadingState';
import { rowClassName } from './rowStyle';
import { useServerPage, type FetchPage, type ServerQuery } from './useServerPage';

export interface DataColumn<T> {
  id: string;
  header: string;
  render: (row: T) => ReactNode;
  /** Server sort field; column is sortable only when set. */
  sortField?: string;
  align?: 'left' | 'right' | 'center';
}

export interface ServerDataTableProps<T> {
  columns: readonly DataColumn<T>[];
  fetchPage: FetchPage<T>;
  getRowId: (row: T) => string;
  /** Extra server-side filters (e.g. status); changing them resets to page 1. */
  filters?: Readonly<Record<string, string | undefined>>;
  searchable?: boolean;
  searchPlaceholder?: string;
  debounceMs?: number;
  /** e.g. `-created_at`. */
  initialSort?: string;
  initialPageSize?: number;
  pageSizeOptions?: number[];
  toolbar?: ReactNode;
  emptyTitle?: string;
  emptyDescription?: string;
  onRowClick?: (row: T) => void;
  /** Inactive records (deactivated, retired, cancelled) are shown muted. */
  isRowMuted?: (row: T) => boolean;
  /** Increment to refetch the current page (e.g. after a mutation). */
  reloadKey?: number;
  /** Told the debounced search text (e.g. so an export can use the same `q`). */
  onSearchChange?: (q: string) => void;
  /** Expandable rows: details shown under the row, toggled by a disclosure button. */
  renderDetail?: (row: T) => ReactNode;
  /** Accessible name of a row's disclosure button (default "Show details"). */
  detailLabel?: (row: T) => string;
}

const NO_FILTERS: Readonly<Record<string, string | undefined>> = {};

function parseSort(sort: string | undefined): { field: string; direction: 'asc' | 'desc' } | null {
  if (sort === undefined || sort === '') return null;
  return sort.startsWith('-')
    ? { field: sort.slice(1), direction: 'desc' }
    : { field: sort, direction: 'asc' };
}

/** Table with server pagination, sorting, filters and debounced search. */
export function ServerDataTable<T>({
  columns,
  fetchPage,
  getRowId,
  filters = NO_FILTERS,
  searchable = true,
  searchPlaceholder = 'Search',
  debounceMs = 300,
  initialSort,
  initialPageSize = 25,
  pageSizeOptions = [10, 25, 50, 100],
  toolbar,
  emptyTitle = 'No records found',
  emptyDescription,
  onRowClick,
  isRowMuted,
  reloadKey = 0,
  onSearchChange,
  renderDetail,
  detailLabel = () => 'Show details',
}: ServerDataTableProps<T>) {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => new Set());
  const [pageState, setPageState] = useState({ resetKey: '', page: 0 });
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [sort, setSort] = useState<string | undefined>(initialSort);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search.trim(), debounceMs);
  // Changing search or filters returns to the first page.
  const resetKey = JSON.stringify([debouncedSearch, filters]);
  const page = pageState.resetKey === resetKey ? pageState.page : 0;
  const setPage = (p: number) => {
    setPageState({ resetKey, page: p });
  };

  const query: ServerQuery = {
    page: page + 1,
    page_size: pageSize,
    filters,
    ...(sort !== undefined ? { sort } : {}),
    ...(debouncedSearch !== '' ? { q: debouncedSearch } : {}),
  };
  const { data, loading, error } = useServerPage(fetchPage, query, reloadKey);
  useEffect(() => {
    onSearchChange?.(debouncedSearch);
  }, [debouncedSearch, onSearchChange]);
  const toggleExpanded = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  // Clickable rows are reachable and operable from the keyboard (Enter / Space), not only by mouse.
  const rowKeyDown = (row: T) => (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (onRowClick === undefined || e.target !== e.currentTarget) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onRowClick(row);
    }
  };
  const columnCount = columns.length + (renderDetail !== undefined ? 1 : 0);
  const activeSort = parseSort(sort);

  const toggleSort = (field: string) => {
    const nextDesc = activeSort?.field === field && activeSort.direction === 'asc';
    setSort(nextDesc ? `-${field}` : field);
    setPage(0);
  };

  const rows = data?.items ?? [];
  return (
    <Paper variant="outlined">
      {(searchable || toolbar !== undefined) && (
        <Box className="flex flex-wrap items-center gap-3 p-3">
          {searchable && (
            <TextField
              size="small"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
              }}
              placeholder={searchPlaceholder}
              slotProps={{
                htmlInput: { 'aria-label': searchPlaceholder },
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                },
              }}
            />
          )}
          {toolbar}
        </Box>
      )}
      {loading && data !== null && <LinearProgress aria-label="Refreshing" />}
      {error !== null ? (
        <Box className="p-3">
          <ErrorState error={error} title="Could not load data" />
        </Box>
      ) : data === null ? (
        <LoadingState />
      ) : rows.length === 0 ? (
        <EmptyState
          title={emptyTitle}
          {...(emptyDescription ? { description: emptyDescription } : {})}
        />
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                {renderDetail !== undefined && (
                  <TableCell padding="checkbox">
                    <span className="sr-only">Details</span>
                  </TableCell>
                )}
                {columns.map((c) => (
                  <TableCell key={c.id} align={c.align ?? 'left'}>
                    {c.sortField !== undefined ? (
                      <TableSortLabel
                        active={activeSort?.field === c.sortField}
                        direction={activeSort?.field === c.sortField ? activeSort.direction : 'asc'}
                        onClick={() => {
                          if (c.sortField !== undefined) toggleSort(c.sortField);
                        }}
                      >
                        {c.header}
                      </TableSortLabel>
                    ) : (
                      c.header
                    )}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((row) => {
                const id = getRowId(row);
                const open = expanded.has(id);
                const detailId = `row-detail-${id}`;
                return (
                  <Fragment key={id}>
                    <TableRow
                      hover={onRowClick !== undefined}
                      className={rowClassName(onRowClick !== undefined, isRowMuted?.(row) === true)}
                      data-muted={isRowMuted?.(row) === true ? 'true' : undefined}
                      tabIndex={onRowClick !== undefined ? 0 : undefined}
                      onKeyDown={onRowClick !== undefined ? rowKeyDown(row) : undefined}
                      sx={
                        onRowClick !== undefined
                          ? {
                              '&:focus-visible': {
                                outline: '2px solid',
                                outlineColor: 'primary.main',
                                outlineOffset: -2,
                              },
                            }
                          : undefined
                      }
                      onClick={
                        onRowClick !== undefined
                          ? () => {
                              onRowClick(row);
                            }
                          : undefined
                      }
                    >
                      {renderDetail !== undefined && (
                        <TableCell padding="checkbox">
                          <IconButton
                            size="small"
                            aria-label={detailLabel(row)}
                            aria-expanded={open}
                            aria-controls={open ? detailId : undefined}
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleExpanded(id);
                            }}
                          >
                            {open ? (
                              <KeyboardArrowDown fontSize="small" />
                            ) : (
                              <KeyboardArrowRight fontSize="small" />
                            )}
                          </IconButton>
                        </TableCell>
                      )}
                      {columns.map((c) => (
                        <TableCell key={c.id} align={c.align ?? 'left'}>
                          {c.render(row)}
                        </TableCell>
                      ))}
                    </TableRow>
                    {renderDetail !== undefined && open && (
                      <TableRow>
                        <TableCell colSpan={columnCount} sx={{ py: 0 }}>
                          <Collapse in={open} unmountOnExit>
                            <Box id={detailId} className="py-3">
                              {renderDetail(row)}
                            </Box>
                          </Collapse>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      <TablePagination
        component="div"
        count={data?.total ?? 0}
        page={page}
        rowsPerPage={pageSize}
        rowsPerPageOptions={pageSizeOptions}
        onPageChange={(_e, p) => {
          setPage(p);
        }}
        onRowsPerPageChange={(e) => {
          setPageSize(Number(e.target.value));
          setPage(0);
        }}
      />
    </Paper>
  );
}
