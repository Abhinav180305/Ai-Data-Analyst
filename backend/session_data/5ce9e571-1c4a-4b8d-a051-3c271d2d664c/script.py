
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\5ce9e571-1c4a-4b8d-a051-3c271d2d664c\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\5ce9e571-1c4a-4b8d-a051-3c271d2d664c")

import matplotlib.pyplot as plt
product_orders = df.groupby('product_id')['orders'].sum()
result = product_orders.sort_values(ascending=False)
# prepare data for pie chart (top 10 products, rest as 'Other')
top_n = 10
top = result.head(top_n)
other = result.iloc[top_n:].sum()
pie_vals = pd.concat([top, pd.Series({'Other': other})])
pie_vals.plot.pie(figsize=(6,6), autopct='%1.1f%%')
plt.title('Orders distribution by product (top 10)')
plt.ylabel('')
plt.tight_layout()
plt.savefig('chart.png')


out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
