import { createPersistedStore } from '$lib/core/utils/persistence/createPersistedStore';
import type { AnnotationSet } from '$lib/map/types';
import type { SupabaseClient } from '@supabase/supabase-js';
import * as annotationsApi from '$lib/data/supabase/annotations';
import type { FeatureCollection } from 'geojson';

interface AnnotationProjectLibrary {
  projects: AnnotationSet[];
}

const PROJECT_LIBRARY_KEY = 'vma-annotation-projects-v1';

export function createAnnotationProjectStore(supabase?: SupabaseClient, userId?: string) {
  const store = createPersistedStore<AnnotationProjectLibrary>({
    key: PROJECT_LIBRARY_KEY,
    defaultValue: { projects: [] },
    debounceMs: 300,
  });

  async function loadFromSupabase() {
    if (!supabase || !userId) return;
    try {
      const projects = await annotationsApi.fetchUserAnnotationSets(supabase, userId);
      if (projects.length > 0) {
        store.set({ projects });
      }
    } catch (err) {
      console.error('Failed to load annotation projects from Supabase:', err);
    }
  }

  loadFromSupabase();

  function createProject(title: string, mapId: string): string {
    const id = crypto.randomUUID();
    const now = Date.now();
    const mapIds = mapId ? [mapId] : [];
    const emptyFeatures: FeatureCollection = { type: 'FeatureCollection', features: [] };
    const project: AnnotationSet = {
      id,
      title,
      mapId,
      mapIds,
      authorId: userId ?? '',
      features: emptyFeatures,
      isPublic: false,
      createdAt: now,
      updatedAt: now,
    };
    store.update((lib) => ({ projects: [...lib.projects, project] }));

    if (supabase && userId) {
      annotationsApi
        .createAnnotationSet(supabase, {
          title,
          mapId,
          mapIds,
          userId,
          features: emptyFeatures,
          isPublic: false,
        })
        .then((sbId) => {
          if (sbId) {
            store.update((lib) => ({
              projects: lib.projects.map((p) => (p.id === id ? { ...p, id: sbId } : p)),
            }));
          }
        });
    }

    return id;
  }

  function updateProject(id: string, updates: Partial<Pick<AnnotationSet, 'title'>>) {
    store.update((lib) => ({
      projects: lib.projects.map((p) =>
        p.id === id ? { ...p, ...updates, updatedAt: Date.now() } : p
      ),
    }));

    if (supabase && userId) {
      annotationsApi.updateAnnotationSet(supabase, id, updates);
    }
  }

  function deleteProject(id: string) {
    store.update((lib) => ({
      projects: lib.projects.filter((p) => p.id !== id),
    }));

    if (supabase && userId) {
      annotationsApi.deleteAnnotationSet(supabase, id);
    }
  }

  function saveFeatures(id: string, features: FeatureCollection, mapIds?: string[]) {
    store.update((lib) => ({
      projects: lib.projects.map((p) =>
        p.id === id ? { ...p, features, mapIds: mapIds ?? p.mapIds, updatedAt: Date.now() } : p
      ),
    }));

    if (supabase && userId) {
      return annotationsApi.updateAnnotationSet(supabase, id, { features, mapIds });
    }
    return Promise.resolve(true);
  }

  return {
    subscribe: store.subscribe,
    set: store.set,
    update: store.update,
    reset: store.reset,
    createProject,
    updateProject,
    deleteProject,
    saveFeatures,
    loadFromSupabase,
  };
}

export type AnnotationProjectStore = ReturnType<typeof createAnnotationProjectStore>;
