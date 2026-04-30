import type { APIRoute } from "astro";
import { adminClient } from "@/lib/supabase";
import { isValidTokenFormat } from "@/lib/tokens";

export const prerender = false;

export const GET: APIRoute = async ({ url }) => {
  const token = url.searchParams.get("token") ?? "";
  if (!isValidTokenFormat(token)) {
    return new Response("Invalid token", { status: 400 });
  }

  const supabase = adminClient();
  const { error, data } = await supabase
    .from("subscribers")
    .update({ status: "confirmed", confirmed_at: new Date().toISOString(), confirm_token: null })
    .eq("confirm_token", token)
    .select();

  if (error || !data || data.length === 0) {
    return new Response("Token not found or already used", { status: 404 });
  }

  return new Response(
    `<html><body style="font-family:sans-serif;max-width:560px;margin:80px auto;padding:24px">
      <h1>구독 확인 완료</h1>
      <p>매일 아침 6시(KST)에 메일이 도착합니다.</p>
      <p><a href="${import.meta.env.SITE_URL}">← 홈으로</a></p>
    </body></html>`,
    { status: 200, headers: { "content-type": "text/html; charset=utf-8" } }
  );
};
