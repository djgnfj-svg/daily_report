/// <reference path="../.astro/types.d.ts" />
/// <reference types="astro/client" />

interface ImportMetaEnv {
  readonly SUPABASE_URL: string;
  readonly SUPABASE_SERVICE_KEY: string;
  readonly RESEND_API_KEY: string;
  readonly SITE_URL: string;
}
interface ImportMeta { readonly env: ImportMetaEnv; }
