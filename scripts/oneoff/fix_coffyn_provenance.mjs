import { createClient } from '@supabase/supabase-js';

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

// Virtual Saigon's own record (ID 1267, virtual-saigon.net/Maps/Collection?ID=1267) lists
// Copyright: "Archives nationales d'outre-mer (ANOM, France)" for this exact map (Coffyn,
// 1862, "Bâtiments civils. Projet de ville de 500 000 âmes à Saigon.") — independent
// confirmation of what the row's own dc_description already said.
const { data, error } = await db
  .from('maps')
  .update({ holding_institution: "Archives nationales d'outre-mer" })
  .eq('slug', 'batiments-civils-le-plan-du-colonel-du-genie-paul-coffyn-pour-une-ville-de-500-0')
  .select('slug,holding_institution');
if (error) throw new Error(error.message);
if (!data.length) throw new Error('no row matched');
console.log(JSON.stringify(data[0]));
