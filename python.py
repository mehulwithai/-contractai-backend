from supabase import create_client
from app.core.config import get_settings
s = get_settings()
sb = create_client(s.supabase_url, s.supabase_service_key)

# Try fetching reviews directly
try:
    r = sb.table('reviews').select('*').limit(1).execute()
    print('reviews table OK:', r)
except Exception as e:
    print('reviews error:', type(e).__name__, str(e))

# Try fetching subscriptions
try:
    r = sb.table('subscriptions').select('*').limit(1).execute()
    print('subscriptions table OK:', r)
except Exception as e:
    print('subscriptions error:', type(e).__name__, str(e))

# Try listing storage buckets
try:
    b = sb.storage.list_buckets()
    print('buckets:', [x.name for x in b])
except Exception as e:
    print('storage error:', type(e).__name__, str(e))
