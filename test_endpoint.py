import sys
import os
sys.path.append('backend')
os.environ['DATABASE_URL'] = 'postgresql://postgres.pmigweggjmzttglpyakk:Yasaswin%401998@aws-1-ap-south-1.pooler.supabase.com:6543/postgres'
from main import export_platform_highlights
try:
    export_platform_highlights('2026-04-30', '2026-05-31')
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
