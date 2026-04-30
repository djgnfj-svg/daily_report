import type { APIRoute } from "astro";
import { adminClient } from "@/lib/supabase";
import { isValidTokenFormat } from "@/lib/tokens";

export const prerender = false;

async function unsubscribe(token: string) {
  if (!isValidTokenFormat(token)) return { ok: false, status: 400, msg: "Invalid token" };
  const { data, error } = await adminClient()
    .from("subscribers")
    .update({ status: "unsubscribed" })
    .eq("unsub_token", token)
    .select();
  if (error || !data || data.length === 0) return { ok: false, status: 404, msg: "Not found" };
  return { ok: true, status: 200, msg: "Unsubscribed" };
}

const html = (msg: string) =>
  `<html><body style="font-family:sans-serif;max-width:560px;margin:80px auto;padding:24px"><h1>${msg}</h1><p><a href="${import.meta.env.SITE_URL}">← 홈으로</a></p></body></html>`;

export const GET: APIRoute = async ({ url }) => {
  const r = await unsubscribe(url.searchParams.get("token") ?? "");
  return new Response(html(r.msg), { status: r.status, headers: { "content-type": "text/html; charset=utf-8" } });
};

export const POST: APIRoute = async ({ url }) => {
  const r = await unsubscribe(url.searchParams.get("token") ?? "");
  return new Response(r.msg, { status: r.status });
};
