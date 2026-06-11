import os
from dotenv import load_dotenv
load_dotenv('backend/.env')
from sqlalchemy import create_engine
import pandas as pd
engine = create_engine(os.environ['DATABASE_URL'])
df = pd.read_sql('SELECT platform, date FROM posts', engine)
print('FB Dates:', df[df.platform=='Facebook']['date'].tolist())
print('IG Dates:', df[df.platform=='Instagram']['date'].tolist())
