import pandas as pd
url='https://docs.google.com/spreadsheets/d/1FxpnOIzGq7iTEj7RHbvzbYFa80qcKs-Y3sYXqoXt2p4/export?format=xlsx'
try:
    xl=pd.ExcelFile(url)
    fb=xl.parse('Raw_FB')
    print('Raw Publish time column:')
    print(fb['Publish time'].head(15).tolist())
except Exception as e:
    print('Error:', e)
