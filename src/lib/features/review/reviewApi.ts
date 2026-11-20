/**
 * The review page's calls to /api/review/**. `fetch` does not throw on 4xx or 5xx, so every reply
 * is checked here and a failure carries its status: the session tells a stale item (409) from a
 * network error from a refusal (400).
 */

import type { NextReply, SearchHit, TaskSummary, VerdictBody } from './types';

export class ReviewApiError extends Error {
  constructor(
    readonly status: number,
    message: string
  ) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ReviewApiError(0, 'No connection. Your verdict is kept; try again.');
  }
  if (!res.ok) {
    let message = res.statusText;
    try {
      message = (await res.json()).message ?? message;
    } catch {
      /* a body that is not JSON keeps the status text */
    }
    throw new ReviewApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

export type ReviewApi = {
  next(task: string): Promise<NextReply>;
  verdict(task: string, body: VerdictBody): Promise<{ ok: true; duplicate: boolean }>;
  undo(task: string): Promise<{ ok: true; undone: string | null }>;
  search(task: string, item: string, q: string): Promise<SearchHit[]>;
};

const post = (body?: unknown): RequestInit => ({
  method: 'POST',
  ...(body === undefined
    ? {}
    : { headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }),
});

export const reviewApi: ReviewApi = {
  next: (task) => call(`/api/review/${task}/next`),
  verdict: (task, body) => call(`/api/review/${task}/verdict`, post(body)),
  undo: (task) => call(`/api/review/${task}/undo`, post()),
  search: async (task, item, q) =>
    (
      await call<{ hits: SearchHit[] }>(
        `/api/review/${task}/search?item=${encodeURIComponent(item)}&q=${encodeURIComponent(q)}`
      )
    ).hits,
};

export const fetchTasks = async (): Promise<TaskSummary[]> =>
  (await call<{ tasks: TaskSummary[] }>('/api/review/tasks')).tasks;
