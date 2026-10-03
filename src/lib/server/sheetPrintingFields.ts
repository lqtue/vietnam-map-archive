import { error } from '@sveltejs/kit';
import type { Database, Json } from '$lib/data/supabase/types';

const fields = [
  'printed_title',
  'edition_statement',
  'edition_label',
  'issuing_agency',
  'content_year',
  'edition_year',
  'printing_year',
  'printing_month',
  'printer',
  'printing_statement',
  'part',
  'evidence',
  'review_status',
] as const;

export function pickSheetPrintingFields(
  body: Record<string, unknown>,
  existing: { evidence?: Json; review_status?: string } = {}
): Database['public']['Tables']['sheet_printings']['Update'] {
  const values: Record<string, unknown> = {};
  for (const field of fields) {
    if (body[field] !== undefined) values[field] = body[field];
  }

  if (values.part === '') values.part = null;
  if (
    values.part != null &&
    values.part !== undefined &&
    !['whole', 'W', 'E', 'assemblage'].includes(String(values.part))
  ) {
    throw error(400, 'Invalid sheet part');
  }
  for (const field of ['content_year', 'edition_year', 'printing_year', 'printing_month']) {
    if (values[field] === '') {
      values[field] = null;
      continue;
    }
    if (values[field] === undefined || values[field] === null) continue;
    if (
      (typeof values[field] !== 'number' && typeof values[field] !== 'string') ||
      (typeof values[field] === 'string' && !values[field].trim()) ||
      !Number.isInteger(Number(values[field]))
    ) {
      throw error(400, `${field} must be a whole number`);
    }
    values[field] = Number(values[field]);
  }
  const reviewStatus = String(values.review_status ?? existing.review_status ?? 'unreviewed');
  if (!['unreviewed', 'verified', 'uncertain'].includes(reviewStatus)) {
    throw error(400, 'Invalid printing review status');
  }

  if (values.evidence === null) throw error(400, 'Evidence must be a JSON object');
  const rawEvidence = values.evidence === undefined ? (existing.evidence ?? {}) : values.evidence;
  if (typeof rawEvidence !== 'object' || rawEvidence === null || Array.isArray(rawEvidence)) {
    throw error(400, 'Evidence must be a JSON object');
  }
  const evidence = rawEvidence as Record<string, unknown>;
  if (reviewStatus === 'verified') {
    const sourceUrl = typeof evidence.source_url === 'string' ? evidence.source_url.trim() : '';
    const reviewNote = typeof evidence.review_note === 'string' ? evidence.review_note.trim() : '';
    if (!sourceUrl || !reviewNote) {
      throw error(400, 'Verified printings require an evidence source URL and review note');
    }
    let parsed: URL;
    try {
      parsed = new URL(sourceUrl);
    } catch {
      throw error(400, 'Evidence source must be an absolute URL');
    }
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      throw error(400, 'Evidence source must use HTTP or HTTPS');
    }
  }

  if (values.evidence !== undefined || reviewStatus !== existing.review_status) {
    values.evidence = evidence as Json;
  }
  if (values.review_status !== undefined) values.review_status = reviewStatus;
  return values as Database['public']['Tables']['sheet_printings']['Update'];
}

export function pickSheetPrintingInsert(body: Record<string, unknown>) {
  const update = pickSheetPrintingFields(body);
  return update as Database['public']['Tables']['sheet_printings']['Insert'];
}
