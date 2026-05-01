"""오늘자 reports/signals/daily_metrics/daily_scores 삭제 (재실행용)."""
from datetime import date
from dotenv import load_dotenv

load_dotenv()
from morningbrief.data.supabase_client import get_client

c = get_client()
today = date.today().isoformat()

rep = c.table("reports").select("id").eq("date", today).execute().data
for r in rep:
    c.table("signals").delete().eq("report_id", r["id"]).execute()
c.table("reports").delete().eq("date", today).execute()
c.table("daily_metrics").delete().eq("date", today).execute()
c.table("daily_scores").delete().eq("date", today).execute()
print(f"purged {today}: reports={len(rep)}")
