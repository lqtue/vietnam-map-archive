export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  graphql_public: {
    Tables: {
      [_ in never]: never
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      graphql: {
        Args: {
          extensions?: Json
          operationName?: string
          query?: string
          variables?: Json
        }
        Returns: Json
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
  public: {
    Tables: {
      annotation_sets: {
        Row: {
          created_at: string
          features: Json
          id: string
          is_public: boolean
          map_id: string | null
          title: string
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          features?: Json
          id?: string
          is_public?: boolean
          map_id?: string | null
          title?: string
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          features?: Json
          id?: string
          is_public?: boolean
          map_id?: string | null
          title?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "annotation_sets_map_id_fk"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "map_pipeline_status"
            referencedColumns: ["map_id"]
          },
          {
            foreignKeyName: "annotation_sets_map_id_fk"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "maps"
            referencedColumns: ["id"]
          },
        ]
      }
      footprint_submissions: {
        Row: {
          category: string | null
          confidence: number | null
          created_at: string | null
          feature_type: string
          geom: unknown
          geom_rmse: number | null
          geom_src: string | null
          id: string
          iiif_canvas: string | null
          map_id: string | null
          name: string | null
          pixel_polygon: Json
          run_id: string | null
          source: string
          status: string
          temporal_status: string
          updated_at: string | null
          user_id: string | null
          valid_from: string | null
          valid_to: string | null
        }
        Insert: {
          category?: string | null
          confidence?: number | null
          created_at?: string | null
          feature_type?: string
          geom?: unknown
          geom_rmse?: number | null
          geom_src?: string | null
          id?: string
          iiif_canvas?: string | null
          map_id?: string | null
          name?: string | null
          pixel_polygon: Json
          run_id?: string | null
          source?: string
          status?: string
          temporal_status?: string
          updated_at?: string | null
          user_id?: string | null
          valid_from?: string | null
          valid_to?: string | null
        }
        Update: {
          category?: string | null
          confidence?: number | null
          created_at?: string | null
          feature_type?: string
          geom?: unknown
          geom_rmse?: number | null
          geom_src?: string | null
          id?: string
          iiif_canvas?: string | null
          map_id?: string | null
          name?: string | null
          pixel_polygon?: Json
          run_id?: string | null
          source?: string
          status?: string
          temporal_status?: string
          updated_at?: string | null
          user_id?: string | null
          valid_from?: string | null
          valid_to?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "footprint_submissions_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "map_pipeline_status"
            referencedColumns: ["map_id"]
          },
          {
            foreignKeyName: "footprint_submissions_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "maps"
            referencedColumns: ["id"]
          },
        ]
      }
      label_pins: {
        Row: {
          created_at: string | null
          data: Json | null
          id: string
          label: string
          map_id: string
          pixel_x: number
          pixel_y: number
          user_id: string
        }
        Insert: {
          created_at?: string | null
          data?: Json | null
          id?: string
          label: string
          map_id: string
          pixel_x: number
          pixel_y: number
          user_id: string
        }
        Update: {
          created_at?: string | null
          data?: Json | null
          id?: string
          label?: string
          map_id?: string
          pixel_x?: number
          pixel_y?: number
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "label_pins_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "map_pipeline_status"
            referencedColumns: ["map_id"]
          },
          {
            foreignKeyName: "label_pins_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "maps"
            referencedColumns: ["id"]
          },
        ]
      }
      map_iiif_sources: {
        Row: {
          created_at: string | null
          id: string
          iiif_image: string
          iiif_manifest: string | null
          is_primary: boolean
          label: string | null
          map_id: string
          sort_order: number
          source_type: string | null
        }
        Insert: {
          created_at?: string | null
          id?: string
          iiif_image: string
          iiif_manifest?: string | null
          is_primary?: boolean
          label?: string | null
          map_id: string
          sort_order?: number
          source_type?: string | null
        }
        Update: {
          created_at?: string | null
          id?: string
          iiif_image?: string
          iiif_manifest?: string | null
          is_primary?: boolean
          label?: string | null
          map_id?: string
          sort_order?: number
          source_type?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "map_iiif_sources_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "map_pipeline_status"
            referencedColumns: ["map_id"]
          },
          {
            foreignKeyName: "map_iiif_sources_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "maps"
            referencedColumns: ["id"]
          },
        ]
      }
      map_opens: {
        Row: {
          created_at: string | null
          id: string
          map_id: string
        }
        Insert: {
          created_at?: string | null
          id?: string
          map_id: string
        }
        Update: {
          created_at?: string | null
          id?: string
          map_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "map_opens_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "map_pipeline_status"
            referencedColumns: ["map_id"]
          },
          {
            foreignKeyName: "map_opens_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "maps"
            referencedColumns: ["id"]
          },
        ]
      }
      map_review_marks: {
        Row: {
          exported_at: string | null
          map_id: string
          reviewed_at: string | null
          seg_reviewed_at: string | null
          updated_at: string
        }
        Insert: {
          exported_at?: string | null
          map_id: string
          reviewed_at?: string | null
          seg_reviewed_at?: string | null
          updated_at?: string
        }
        Update: {
          exported_at?: string | null
          map_id?: string
          reviewed_at?: string | null
          seg_reviewed_at?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "map_review_marks_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: true
            referencedRelation: "map_pipeline_status"
            referencedColumns: ["map_id"]
          },
          {
            foreignKeyName: "map_review_marks_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: true
            referencedRelation: "maps"
            referencedColumns: ["id"]
          },
        ]
      }
      map_slug_aliases: {
        Row: {
          created_at: string | null
          map_id: string
          slug: string
        }
        Insert: {
          created_at?: string | null
          map_id: string
          slug: string
        }
        Update: {
          created_at?: string | null
          map_id?: string
          slug?: string
        }
        Relationships: [
          {
            foreignKeyName: "map_slug_aliases_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "map_pipeline_status"
            referencedColumns: ["map_id"]
          },
          {
            foreignKeyName: "map_slug_aliases_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "maps"
            referencedColumns: ["id"]
          },
        ]
      }
      maps: {
        Row: {
          allmaps_id: string | null
          annotation_url: string | null
          bbox: number[] | null
          collection: string | null
          created_at: string | null
          created_by: string | null
          creator: string | null
          dc_coverage: string | null
          dc_description: string | null
          dc_publisher: string | null
          dc_subject: string | null
          extra_metadata: Json | null
          georef_done: boolean
          help_needed: boolean
          holding_institution: string | null
          ia_identifier: string | null
          id: string
          iiif_image: string | null
          iiif_manifest: string | null
          label_config: Json
          language: string | null
          legend_done: boolean
          location: string | null
          map_type: string | null
          name: string
          original_title: string | null
          physical_description: string | null
          priority: number
          rights: string | null
          search_vector: unknown
          shelfmark: string | null
          slug: string
          source_type: string | null
          source_url: string | null
          status: string | null
          thumbnail: string | null
          triage: Json
          updated_at: string | null
          year: number | null
          year_label: string | null
        }
        Insert: {
          allmaps_id?: string | null
          annotation_url?: string | null
          bbox?: number[] | null
          collection?: string | null
          created_at?: string | null
          created_by?: string | null
          creator?: string | null
          dc_coverage?: string | null
          dc_description?: string | null
          dc_publisher?: string | null
          dc_subject?: string | null
          extra_metadata?: Json | null
          georef_done?: boolean
          help_needed?: boolean
          holding_institution?: string | null
          ia_identifier?: string | null
          id?: string
          iiif_image?: string | null
          iiif_manifest?: string | null
          label_config?: Json
          language?: string | null
          legend_done?: boolean
          location?: string | null
          map_type?: string | null
          name: string
          original_title?: string | null
          physical_description?: string | null
          priority?: number
          rights?: string | null
          search_vector?: unknown
          shelfmark?: string | null
          slug?: string
          source_type?: string | null
          source_url?: string | null
          status?: string | null
          thumbnail?: string | null
          triage?: Json
          updated_at?: string | null
          year?: number | null
          year_label?: string | null
        }
        Update: {
          allmaps_id?: string | null
          annotation_url?: string | null
          bbox?: number[] | null
          collection?: string | null
          created_at?: string | null
          created_by?: string | null
          creator?: string | null
          dc_coverage?: string | null
          dc_description?: string | null
          dc_publisher?: string | null
          dc_subject?: string | null
          extra_metadata?: Json | null
          georef_done?: boolean
          help_needed?: boolean
          holding_institution?: string | null
          ia_identifier?: string | null
          id?: string
          iiif_image?: string | null
          iiif_manifest?: string | null
          label_config?: Json
          language?: string | null
          legend_done?: boolean
          location?: string | null
          map_type?: string | null
          name?: string
          original_title?: string | null
          physical_description?: string | null
          priority?: number
          rights?: string | null
          search_vector?: unknown
          shelfmark?: string | null
          slug?: string
          source_type?: string | null
          source_url?: string | null
          status?: string | null
          thumbnail?: string | null
          triage?: Json
          updated_at?: string | null
          year?: number | null
          year_label?: string | null
        }
        Relationships: []
      }
      ocr_extractions: {
        Row: {
          category: string
          category_validated: string | null
          confidence: number
          created_at: string
          footprint_id: string | null
          geom: unknown
          geom_rmse: number | null
          geom_src: string | null
          global_h: number | null
          global_w: number | null
          global_x: number
          global_xi: number | null
          global_y: number
          global_yi: number | null
          id: string
          label_h: number | null
          label_w: number | null
          map_id: string
          model: string | null
          notes: string | null
          prompt: string | null
          rotation_deg: number | null
          run_id: string
          status: string
          text: string
          text_validated: string | null
          tile_h: number
          tile_w: number
          tile_x: number
          tile_y: number
          validated_at: string | null
          validated_by: string | null
        }
        Insert: {
          category: string
          category_validated?: string | null
          confidence?: number
          created_at?: string
          footprint_id?: string | null
          geom?: unknown
          geom_rmse?: number | null
          geom_src?: string | null
          global_h?: number | null
          global_w?: number | null
          global_x: number
          global_xi?: number | null
          global_y: number
          global_yi?: number | null
          id?: string
          label_h?: number | null
          label_w?: number | null
          map_id: string
          model?: string | null
          notes?: string | null
          prompt?: string | null
          rotation_deg?: number | null
          run_id: string
          status?: string
          text: string
          text_validated?: string | null
          tile_h: number
          tile_w: number
          tile_x: number
          tile_y: number
          validated_at?: string | null
          validated_by?: string | null
        }
        Update: {
          category?: string
          category_validated?: string | null
          confidence?: number
          created_at?: string
          footprint_id?: string | null
          geom?: unknown
          geom_rmse?: number | null
          geom_src?: string | null
          global_h?: number | null
          global_w?: number | null
          global_x?: number
          global_xi?: number | null
          global_y?: number
          global_yi?: number | null
          id?: string
          label_h?: number | null
          label_w?: number | null
          map_id?: string
          model?: string | null
          notes?: string | null
          prompt?: string | null
          rotation_deg?: number | null
          run_id?: string
          status?: string
          text?: string
          text_validated?: string | null
          tile_h?: number
          tile_w?: number
          tile_x?: number
          tile_y?: number
          validated_at?: string | null
          validated_by?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "ocr_extractions_footprint_id_fkey"
            columns: ["footprint_id"]
            isOneToOne: false
            referencedRelation: "footprint_submissions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "ocr_extractions_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "map_pipeline_status"
            referencedColumns: ["map_id"]
          },
          {
            foreignKeyName: "ocr_extractions_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "maps"
            referencedColumns: ["id"]
          },
        ]
      }
      pipeline_jobs: {
        Row: {
          attempts: number
          claimed_at: string | null
          created_at: string
          error: string | null
          finished_at: string | null
          id: string
          kind: string
          map_id: string | null
          max_attempts: number
          payload: Json
          priority: number
          result: Json | null
          started_at: string | null
          status: string
          updated_at: string
          worker: string | null
        }
        Insert: {
          attempts?: number
          claimed_at?: string | null
          created_at?: string
          error?: string | null
          finished_at?: string | null
          id?: string
          kind: string
          map_id?: string | null
          max_attempts?: number
          payload?: Json
          priority?: number
          result?: Json | null
          started_at?: string | null
          status?: string
          updated_at?: string
          worker?: string | null
        }
        Update: {
          attempts?: number
          claimed_at?: string | null
          created_at?: string
          error?: string | null
          finished_at?: string | null
          id?: string
          kind?: string
          map_id?: string | null
          max_attempts?: number
          payload?: Json
          priority?: number
          result?: Json | null
          started_at?: string | null
          status?: string
          updated_at?: string
          worker?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "pipeline_jobs_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "map_pipeline_status"
            referencedColumns: ["map_id"]
          },
          {
            foreignKeyName: "pipeline_jobs_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "maps"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          created_at: string | null
          display_name: string | null
          id: string
          role: string | null
        }
        Insert: {
          created_at?: string | null
          display_name?: string | null
          id: string
          role?: string | null
        }
        Update: {
          created_at?: string | null
          display_name?: string | null
          id?: string
          role?: string | null
        }
        Relationships: []
      }
      scout_candidates: {
        Row: {
          category: string | null
          collection: string | null
          created_at: string
          creator: string | null
          date: string | null
          external_id: string
          found_via: string | null
          holding_institution: string | null
          id: string
          language: string | null
          manifest_url: string | null
          map_id: string | null
          publisher: string | null
          raw: Json | null
          reasons: string | null
          review_note: string | null
          reviewed_at: string | null
          reviewer_id: string | null
          rights: string | null
          score: number
          search_vector: unknown
          source: string
          source_url: string | null
          status: string
          thumbnail: string | null
          title: string
          year: number | null
        }
        Insert: {
          category?: string | null
          collection?: string | null
          created_at?: string
          creator?: string | null
          date?: string | null
          external_id: string
          found_via?: string | null
          holding_institution?: string | null
          id?: string
          language?: string | null
          manifest_url?: string | null
          map_id?: string | null
          publisher?: string | null
          raw?: Json | null
          reasons?: string | null
          review_note?: string | null
          reviewed_at?: string | null
          reviewer_id?: string | null
          rights?: string | null
          score?: number
          search_vector?: unknown
          source: string
          source_url?: string | null
          status?: string
          thumbnail?: string | null
          title: string
          year?: number | null
        }
        Update: {
          category?: string | null
          collection?: string | null
          created_at?: string
          creator?: string | null
          date?: string | null
          external_id?: string
          found_via?: string | null
          holding_institution?: string | null
          id?: string
          language?: string | null
          manifest_url?: string | null
          map_id?: string | null
          publisher?: string | null
          raw?: Json | null
          reasons?: string | null
          review_note?: string | null
          reviewed_at?: string | null
          reviewer_id?: string | null
          rights?: string | null
          score?: number
          search_vector?: unknown
          source?: string
          source_url?: string | null
          status?: string
          thumbnail?: string | null
          title?: string
          year?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "scout_candidates_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "map_pipeline_status"
            referencedColumns: ["map_id"]
          },
          {
            foreignKeyName: "scout_candidates_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "maps"
            referencedColumns: ["id"]
          },
        ]
      }
      series_sheets: {
        Row: {
          bbox: number[] | null
          created_at: string
          edition: string | null
          held_by: string | null
          map_id: string | null
          name: string | null
          note: string | null
          series_key: string
          sheet_number: string
          source: string | null
          source_ref: string | null
          updated_at: string
          year: number | null
        }
        Insert: {
          bbox?: number[] | null
          created_at?: string
          edition?: string | null
          held_by?: string | null
          map_id?: string | null
          name?: string | null
          note?: string | null
          series_key: string
          sheet_number: string
          source?: string | null
          source_ref?: string | null
          updated_at?: string
          year?: number | null
        }
        Update: {
          bbox?: number[] | null
          created_at?: string
          edition?: string | null
          held_by?: string | null
          map_id?: string | null
          name?: string | null
          note?: string | null
          series_key?: string
          sheet_number?: string
          source?: string | null
          source_ref?: string | null
          updated_at?: string
          year?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "series_sheets_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "map_pipeline_status"
            referencedColumns: ["map_id"]
          },
          {
            foreignKeyName: "series_sheets_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "maps"
            referencedColumns: ["id"]
          },
        ]
      }
      sheet_sources: {
        Row: {
          created_at: string
          edition: string | null
          id: string
          institution: string
          note: string | null
          part: string | null
          rights: string | null
          series_key: string
          sheet_number: string
          source_ref: string
          title: string | null
          updated_at: string
          url: string | null
          year: number | null
        }
        Insert: {
          created_at?: string
          edition?: string | null
          id?: string
          institution: string
          note?: string | null
          part?: string | null
          rights?: string | null
          series_key: string
          sheet_number: string
          source_ref: string
          title?: string | null
          updated_at?: string
          url?: string | null
          year?: number | null
        }
        Update: {
          created_at?: string
          edition?: string | null
          id?: string
          institution?: string
          note?: string | null
          part?: string | null
          rights?: string | null
          series_key?: string
          sheet_number?: string
          source_ref?: string
          title?: string | null
          updated_at?: string
          url?: string | null
          year?: number | null
        }
        Relationships: []
      }
      stories: {
        Row: {
          created_at: string
          description: string | null
          id: string
          mode: string
          region: Json
          reviewed_at: string | null
          reviewed_by: string | null
          status: string
          title: string
          updated_at: string
          user_id: string | null
        }
        Insert: {
          created_at?: string
          description?: string | null
          id?: string
          mode?: string
          region?: Json
          reviewed_at?: string | null
          reviewed_by?: string | null
          status?: string
          title: string
          updated_at?: string
          user_id?: string | null
        }
        Update: {
          created_at?: string
          description?: string | null
          id?: string
          mode?: string
          region?: Json
          reviewed_at?: string | null
          reviewed_by?: string | null
          status?: string
          title?: string
          updated_at?: string
          user_id?: string | null
        }
        Relationships: []
      }
      story_points: {
        Row: {
          camera: Json
          challenge: Json
          created_at: string
          description: string | null
          hint: string | null
          id: string
          interaction: string
          lat: number
          lon: number
          overlay_map_id: string | null
          sort_order: number
          story_id: string
          title: string
          trigger_radius: number
        }
        Insert: {
          camera?: Json
          challenge?: Json
          created_at?: string
          description?: string | null
          hint?: string | null
          id?: string
          interaction?: string
          lat: number
          lon: number
          overlay_map_id?: string | null
          sort_order?: number
          story_id: string
          title: string
          trigger_radius?: number
        }
        Update: {
          camera?: Json
          challenge?: Json
          created_at?: string
          description?: string | null
          hint?: string | null
          id?: string
          interaction?: string
          lat?: number
          lon?: number
          overlay_map_id?: string | null
          sort_order?: number
          story_id?: string
          title?: string
          trigger_radius?: number
        }
        Relationships: [
          {
            foreignKeyName: "story_points_overlay_map_id_fkey"
            columns: ["overlay_map_id"]
            isOneToOne: false
            referencedRelation: "map_pipeline_status"
            referencedColumns: ["map_id"]
          },
          {
            foreignKeyName: "story_points_overlay_map_id_fkey"
            columns: ["overlay_map_id"]
            isOneToOne: false
            referencedRelation: "maps"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "story_points_story_id_fkey"
            columns: ["story_id"]
            isOneToOne: false
            referencedRelation: "stories"
            referencedColumns: ["id"]
          },
        ]
      }
      user_favorites: {
        Row: {
          created_at: string | null
          id: string
          map_id: string
          user_id: string
        }
        Insert: {
          created_at?: string | null
          id?: string
          map_id: string
          user_id: string
        }
        Update: {
          created_at?: string | null
          id?: string
          map_id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "user_favorites_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "map_pipeline_status"
            referencedColumns: ["map_id"]
          },
          {
            foreignKeyName: "user_favorites_map_id_fkey"
            columns: ["map_id"]
            isOneToOne: false
            referencedRelation: "maps"
            referencedColumns: ["id"]
          },
        ]
      }
      worker_keys: {
        Row: {
          created_at: string
          id: string
          kinds: string[]
          last_seen_at: string | null
          name: string
          revoked_at: string | null
          token_hash: string
        }
        Insert: {
          created_at?: string
          id?: string
          kinds?: string[]
          last_seen_at?: string | null
          name: string
          revoked_at?: string | null
          token_hash: string
        }
        Update: {
          created_at?: string
          id?: string
          kinds?: string[]
          last_seen_at?: string | null
          name?: string
          revoked_at?: string | null
          token_hash?: string
        }
        Relationships: []
      }
    }
    Views: {
      map_pipeline_status: {
        Row: {
          exported_at: string | null
          map_id: string | null
          ocr_finished_at: string | null
          ocr_run_id: string | null
          ocr_started_at: string | null
          reviewed_at: string | null
          seg_finished_at: string | null
          seg_reviewed_at: string | null
          seg_run_id: string | null
          seg_started_at: string | null
          stage: string | null
          updated_at: string | null
        }
        Relationships: []
      }
      map_series: {
        Row: {
          bounds: number[] | null
          collection: string | null
          first_year: number | null
          key: string | null
          last_year: number | null
          name: string | null
          published_sheets: number | null
          sheets: number | null
          survey_sheets: number | null
        }
        Relationships: []
      }
      place_names: {
        Row: {
          category: string | null
          core_key: string | null
          first_year: number | null
          geom_rmse: number | null
          last_year: number | null
          lat: number | null
          lng: number | null
          map_ids: string[] | null
          mentions: number | null
          name: string | null
          name_key: string | null
          variants: string[] | null
          years: number[] | null
        }
        Relationships: []
      }
    }
    Functions: {
      canonicalise_category: { Args: { raw: string }; Returns: string }
      claim_job: {
        Args: { p_kinds: string[]; p_worker: string }
        Returns: {
          attempts: number
          claimed_at: string | null
          created_at: string
          error: string | null
          finished_at: string | null
          id: string
          kind: string
          map_id: string | null
          max_attempts: number
          payload: Json
          priority: number
          result: Json | null
          started_at: string | null
          status: string
          updated_at: string
          worker: string | null
        }
        SetofOptions: {
          from: "*"
          to: "pipeline_jobs"
          isOneToOne: true
          isSetofReturn: false
        }
      }
      context_at: {
        Args: {
          p_lat: number
          p_limit?: number
          p_lng: number
          p_public_only?: boolean
          p_radius_m?: number
          p_year_from?: number
          p_year_to?: number
        }
        Returns: Json
      }
      f_unaccent: { Args: { "": string }; Returns: string }
      finish_job: {
        Args: {
          p_error?: string
          p_id: string
          p_result?: Json
          p_status: string
        }
        Returns: {
          attempts: number
          claimed_at: string | null
          created_at: string
          error: string | null
          finished_at: string | null
          id: string
          kind: string
          map_id: string | null
          max_attempts: number
          payload: Json
          priority: number
          result: Json | null
          started_at: string | null
          status: string
          updated_at: string
          worker: string | null
        }
        SetofOptions: {
          from: "*"
          to: "pipeline_jobs"
          isOneToOne: true
          isSetofReturn: false
        }
      }
      label_key: {
        Args: { p_text: string; p_validated: string }
        Returns: string
      }
      map_context: {
        Args: { p_geom_src?: string; p_map_id: string; p_public_only?: boolean }
        Returns: Json
      }
      map_slug_base: { Args: { p_name: string }; Returns: string }
      map_slug_mint: {
        Args: {
          p_except: string
          p_forbid?: string
          p_name: string
          p_year: number
        }
        Returns: string
      }
      map_slug_taken: {
        Args: { p_except: string; p_slug: string }
        Returns: boolean
      }
      place_core_key: {
        Args: { p_text: string; p_validated: string }
        Returns: string
      }
      place_generic_words: { Args: never; Returns: string }
      place_key: {
        Args: { p_text: string; p_validated: string }
        Returns: string
      }
      revert_recent_validations: {
        Args: { p_map_id: string; p_user: string; p_window_mins?: number }
        Returns: number
      }
      search_labels: {
        Args: { p_limit?: number; p_public_only?: boolean; p_q: string }
        Returns: {
          category: string
          confidence: number
          geom_rmse: number
          h: number
          id: string
          label: string
          lat: number
          lng: number
          map_id: string
          sim: number
          w: number
          x: number
          y: number
        }[]
      }
      series_key: { Args: { p_collection: string }; Returns: string }
      set_extraction_geom: { Args: { p_rows: Json }; Returns: number }
      set_extraction_status: {
        Args: {
          p_ids?: string[]
          p_map_id?: string
          p_run_id?: string
          p_status: string
          p_user: string
        }
        Returns: number
      }
      set_footprint_geom: { Args: { p_rows: Json }; Returns: number }
      set_footprint_status: {
        Args: {
          p_category?: string
          p_feature_type?: string
          p_id: string
          p_name?: string
          p_pixel_polygon?: Json
          p_status: string
          p_user: string
        }
        Returns: {
          category: string | null
          confidence: number | null
          created_at: string | null
          feature_type: string
          geom: unknown
          geom_rmse: number | null
          geom_src: string | null
          id: string
          iiif_canvas: string | null
          map_id: string | null
          name: string | null
          pixel_polygon: Json
          run_id: string | null
          source: string
          status: string
          temporal_status: string
          updated_at: string | null
          user_id: string | null
          valid_from: string | null
          valid_to: string | null
        }
        SetofOptions: {
          from: "*"
          to: "footprint_submissions"
          isOneToOne: true
          isSetofReturn: false
        }
      }
      set_review_mark: {
        Args: { p_map_id: string; p_stage: string; p_user: string }
        Returns: {
          exported_at: string | null
          map_id: string
          reviewed_at: string | null
          seg_reviewed_at: string | null
          updated_at: string
        }
        SetofOptions: {
          from: "*"
          to: "map_review_marks"
          isOneToOne: true
          isSetofReturn: false
        }
      }
      set_story_status: {
        Args: { p_id: string; p_status: string; p_user: string }
        Returns: {
          created_at: string
          description: string | null
          id: string
          mode: string
          region: Json
          reviewed_at: string | null
          reviewed_by: string | null
          status: string
          title: string
          updated_at: string
          user_id: string | null
        }
        SetofOptions: {
          from: "*"
          to: "stories"
          isOneToOne: true
          isSetofReturn: false
        }
      }
      set_triage_key: {
        Args: { p_key: string; p_map_id: string; p_value: Json }
        Returns: Json
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  graphql_public: {
    Enums: {},
  },
  public: {
    Enums: {},
  },
} as const
