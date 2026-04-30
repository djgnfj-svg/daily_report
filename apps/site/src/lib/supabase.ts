import { createClient } from "@supabase/supabase-js";

export function adminClient() {
  return createClient(
    import.meta.env.SUPABASE_URL,
    import.meta.env.SUPABASE_SERVICE_KEY,
    { auth: { persistSession: false } }
  );
}
