/** Give PostgREST's plain error objects a stack and a useful server log. */
export function queryError(context: string, error: unknown): Error {
  const fields =
    error && typeof error === 'object'
      ? (error as { code?: unknown; message?: unknown })
      : {};
  const code = typeof fields.code === 'string' ? fields.code : '';
  const message = typeof fields.message === 'string' ? fields.message : 'Database query failed';
  return new Error(`${context}: ${[code, message].filter(Boolean).join(' ')}`, { cause: error });
}
