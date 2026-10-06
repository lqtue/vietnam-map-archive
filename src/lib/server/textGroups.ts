import { adminClient } from './supabaseAdmin';
import { dbError } from './http';

import { missingTextGroupColumns } from '$lib/core/utils/textGroupSchema';

/** No negative cache: grouping becomes available as soon as the migration lands. */
export async function textGroupsAvailable(db: ReturnType<typeof adminClient>): Promise<boolean> {
  const { error } = await db
    .from('ocr_labels')
    .select('is_text_group,text_group_id,text_group_order')
    .limit(0);
  if (missingTextGroupColumns(error)) return false;
  if (error) dbError(error, 'Could not check text grouping availability');
  return true;
}
