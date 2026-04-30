import { Resend } from "resend";

export async function sendConfirmEmail(to: string, confirmUrl: string) {
  const resend = new Resend(import.meta.env.RESEND_API_KEY);
  return resend.emails.send({
    from: "MorningBrief <hello@reseeall.com>",
    to,
    subject: "MorningBrief 구독 확인",
    html: `
      <h2>MorningBrief 구독 확인</h2>
      <p>아래 버튼을 클릭하면 구독이 활성화됩니다.</p>
      <p><a href="${confirmUrl}" style="display:inline-block;padding:12px 24px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px">구독 확인</a></p>
      <p style="color:#64748b;font-size:13px">본인이 신청하지 않았다면 이 메일을 무시하세요.</p>
    `,
  });
}
