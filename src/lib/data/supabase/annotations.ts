import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from './types';
import type { AnnotationSet } from '$lib/map/types';

type DbAnnotationSet = Database['public']['Tables']['annotation_sets']['Row'];
type AnnotationSetInsert = Database['public']['Tables']['annotation_sets']['Insert'];
type AnnotationSetUpdate = Database['public']['Tables']['annotation_sets']['Update'];

/**
 * `mapIds` rides as a foreign member on the `features` jsonb blob rather than
 * its own column — GeoJSON readers (OL included) ignore unknown top-level
 * keys, and every write path already sends `features` whole, so this needs no
 * migration. `stripMapIds`/`withMapIds` keep that encoding out of the rest of
 * the app, which only ever sees a clean FeatureCollection.
 */
function stripMapIds(raw: unknown): { features: AnnotationSet['features']; mapIds: string[] } {
	const obj = (raw ?? {}) as { mapIds?: unknown; [key: string]: unknown };
	const mapIds = Array.isArray(obj.mapIds) ? obj.mapIds.filter((x) => typeof x === 'string') : [];
	const { mapIds: _drop, ...features } = obj;
	return { features: features as unknown as AnnotationSet['features'], mapIds };
}

function withMapIds(features: object, mapIds: string[]): object {
	return { ...features, mapIds };
}

function toAnnotationSet(row: DbAnnotationSet): AnnotationSet {
	const { features, mapIds } = stripMapIds(row.features);
	return {
		id: row.id,
		title: row.title,
		mapId: row.map_id ?? '',
		mapIds: mapIds.length ? mapIds : [row.map_id].filter((x): x is string => !!x),
		authorId: row.user_id ?? '',
		features,
		isPublic: row.is_public,
		createdAt: new Date(row.created_at).getTime(),
		updatedAt: new Date(row.updated_at).getTime()
	};
}

export async function fetchUserAnnotationSets(
	supabase: SupabaseClient<Database>,
	userId: string
): Promise<AnnotationSet[]> {
	const { data, error } = await supabase
		.from('annotation_sets')
		.select('*')
		.eq('user_id', userId)
		.order('updated_at', { ascending: false });

	if (error || !data) {
		console.error('Failed to fetch annotation sets:', error);
		return [];
	}

	return (data as DbAnnotationSet[]).map(toAnnotationSet);
}


export async function createAnnotationSet(
	supabase: SupabaseClient<Database>,
	params: {
		title: string;
		mapId: string;
		mapIds: string[];
		userId: string;
		features: object;
		isPublic: boolean;
	}
): Promise<string | null> {
	const { data, error } = await supabase
		.from('annotation_sets')
		.insert({
			title: params.title,
			map_id: params.mapId,
			user_id: params.userId,
			features: withMapIds(params.features, params.mapIds),
			is_public: params.isPublic
		} as AnnotationSetInsert)
		.select('id')
		.single();

	if (error) {
		console.error('Failed to create annotation set:', error);
		return null;
	}

	return (data as { id: string }).id;
}

export async function updateAnnotationSet(
	supabase: SupabaseClient<Database>,
	id: string,
	updates: Partial<{
		title: string;
		features: object;
		/** Only applied when `features` is also present — see `stripMapIds`. */
		mapIds: string[];
		is_public: boolean;
	}>
): Promise<boolean> {
	const { mapIds, ...rest } = updates;
	const payload =
		rest.features && mapIds ? { ...rest, features: withMapIds(rest.features, mapIds) } : rest;
	const { error } = await supabase
		.from('annotation_sets')
		.update({ ...payload, updated_at: new Date().toISOString() } as AnnotationSetUpdate)
		.eq('id', id);

	if (error) {
		console.error('Failed to update annotation set:', error);
		return false;
	}
	return true;
}

export async function deleteAnnotationSet(
	supabase: SupabaseClient<Database>,
	id: string
): Promise<boolean> {
	const { error } = await supabase
		.from('annotation_sets')
		.delete()
		.eq('id', id);

	if (error) {
		console.error('Failed to delete annotation set:', error);
		return false;
	}
	return true;
}
