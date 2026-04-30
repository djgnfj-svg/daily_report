import type { APIRoute } from "astro";
import { adminClient } from "@/lib/supabase";
import { sendConfirmEmail } from "@/lib/resend";
import { generateToken } from "@/lib/tokens";

export const prerender = false;

export const POST: APIRoute = async ({ request }) => {
  let body: { email?: string };
  try { body = await request.json(); }
  catch { return new Response(JSON.stringify({ error: "Invalid JSON" }), { status: 400 }); }

  const email = (body.email ?? "").trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return new Response(JSON.stringify({ error: "Invalid email" }), { status: 400 });
  }

  const supabase = adminClient();
  const confirmToken = generateToken();
  const unsubToken = generateToken();

  const { error } = await supabase
    .from("subscribers")
    .upsert(
      { email, status: "pending", confirm_token: confirmToken, unsub_token: unsubToken },
      { onConflict: "email" }
    );
  if (error) {
    return new Response(JSON.stringify({ error: "DB error" }), { status: 500 });
  }

  const confirmUrl = `${import.meta.env.SITE_URL}/api/confirm?token=${confirmToken}`;
  await sendConfirmEmail(email, confirmUrl);

  return new Response(JSON.stringify({ ok: true }), {
    status: 200, headers: { "content-type": "application/json" },
  });
};
