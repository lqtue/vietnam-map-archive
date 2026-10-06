export type OcrExtraction = {
  id: string;
  is_text_group?: boolean;
  text_group_id?: string | null;
  text_group_order?: number | null;
  tile_x: number;
  tile_y: number;
  tile_w: number;
  tile_h: number;
  global_x: number;
  global_y: number;
  global_w: number;
  global_h: number;
  category: string;
  text: string;
  text_validated: string | null;
  category_validated: string | null;
  confidence: number;
  status: 'pending' | 'validated' | 'rejected';
  run_id?: string;
  /** The label's own rectangle (mig 076): length along the text and across it. */
  rotation_deg?: number | null;
  label_w?: number | null;
  label_h?: number | null;
  notes?: string | null;
  validated_at?: string | null;
  model?: string | null;
  prompt?: string | null;
  /** client-side edit buffer, never persisted */
  _editText?: string;
  _editCategory?: string;
  /** A verdict not yet saved — `status` stays what the server holds until it is. */
  _editStatus?: 'pending' | 'validated' | 'rejected';
  _saving?: boolean;
  /** Any local change, including geometry or group membership. */
  _draft?: boolean;
};

/** An extraction whose client-side edit buffer has been seeded (see `withEditState`). */
export type EditableOcrExtraction = OcrExtraction & {
  _editText: string;
  _editCategory: string;
  _editStatus: 'pending' | 'validated' | 'rejected';
  _saving: boolean;
};
