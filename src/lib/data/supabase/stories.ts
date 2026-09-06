import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from './types';
import type { Story, StoryMode, StoryPoint } from '$lib/features/stories/shared/types';

type Json = Database['public']['Tables']['stories']['Row']['region'];
type StoryRow = Database['public']['Tables']['stories']['Row'];
type StoryPointRow = Database['public']['Tables']['story_points']['Row'];
type StoryWithPoints = StoryRow & { story_points?: StoryPointRow[] };

// ─── Row → Type mappers ──────────────────────────────────────────────────────

function rowToPoint(row: StoryPointRow): StoryPoint {
	return {
		id: row.id,
		order: row.sort_order,
		title: row.title,
		description: row.description ?? '',
		hint: row.hint ?? undefined,
		coordinates: [row.lon, row.lat],
		triggerRadius: row.trigger_radius,
		interaction: row.interaction as StoryPoint['interaction'],
		challenge: (row.challenge as unknown as StoryPoint['challenge']) ?? { type: 'none' },
		overlayMapId: row.overlay_map_id ?? undefined,
		camera:
			row.camera && Object.keys(row.camera).length
				? (row.camera as unknown as StoryPoint['camera'])
				: undefined,
	};
}

function rowToStory(row: StoryWithPoints): Story {
	const points: StoryPoint[] = (row.story_points ?? [])
		.slice()
		.sort((a, b) => a.sort_order - b.sort_order)
		.map(rowToPoint);

	return {
		id: row.id,
		authorId: row.user_id ?? '',
		title: row.title,
		description: row.description ?? '',
		mode: row.mode as StoryMode,
		region:
			row.region && Object.keys(row.region).length
				? (row.region as unknown as Story['region'])
				: undefined,
		status: row.status as Story['status'],
		points,
		createdAt: new Date(row.created_at).getTime(),
		updatedAt: new Date(row.updated_at).getTime(),
	};
}

// ─── Public API ──────────────────────────────────────────────────────────────


export async function fetchStoryById(supabase: SupabaseClient<Database>, id: string): Promise<Story | null> {
	const { data, error } = await supabase
		.from('stories')
		.select('*, story_points(*)')
		.eq('id', id)
		.single();
	if (error || !data) { console.error('fetchStoryById:', error); return null; }
	return rowToStory(data as StoryWithPoints);
}

export async function fetchPublicStories(supabase: SupabaseClient<Database>): Promise<Story[]> {
	const { data, error } = await supabase
		.from('stories')
		.select('*, story_points(*)')
		.eq('status', 'approved')
		.order('updated_at', { ascending: false });

	if (error) { console.error('fetchPublicStories:', error); return []; }
	return ((data ?? []) as StoryWithPoints[]).map(rowToStory);
}

/**
 * Push the full local draft (story row + every point) to Supabase, then return.
 * Used by /explore?mode=story's Publish toggle: local drafts only live in localStorage, so
 * before submitting for review we have to make sure the row actually exists.
 *
 * Strategy: upsert the story row by id, then replace all child story_points
 * (delete + insert). Atomic enough for a single user editing one draft at a time.
 */
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function syncStoryToSupabase(
	supabase: SupabaseClient<Database>,
	story: Story,
	userId: string
): Promise<boolean> {
	const { error: storyErr } = await supabase.from('stories').upsert({
		id: story.id,
		user_id: userId,
		title: story.title,
		description: story.description || null,
		mode: story.mode ?? 'guided',
		region: (story.region ?? {}) as unknown as Json,
		status: story.status
	});
	if (storyErr) { console.error('syncStoryToSupabase (story):', storyErr); return false; }

	const { error: delErr } = await supabase
		.from('story_points')
		.delete()
		.eq('story_id', story.id);
	if (delErr) { console.error('syncStoryToSupabase (delete points):', delErr); return false; }

	if (story.points.length > 0) {
		const rows = story.points.map((p, i) => ({
			story_id: story.id,
			sort_order: i,
			title: p.title || `Point ${i + 1}`,
			description: p.description || null,
			hint: p.hint || null,
			lon: p.coordinates[0],
			lat: p.coordinates[1],
			trigger_radius: p.triggerRadius ?? 10,
			interaction: p.interaction ?? 'proximity',
			challenge: (p.challenge ?? { type: 'none' }) as unknown as Json,
			// Schema FKs to maps(id); a legacy allmaps_id (16-hex) would violate the FK.
			overlay_map_id: p.overlayMapId && UUID_RE.test(p.overlayMapId) ? p.overlayMapId : null,
			camera: (p.camera ?? {}) as unknown as Json
		}));
		const { error: insErr } = await supabase.from('story_points').insert(rows);
		if (insErr) { console.error('syncStoryToSupabase (insert points):', insErr); return false; }
	}

	return true;
}

