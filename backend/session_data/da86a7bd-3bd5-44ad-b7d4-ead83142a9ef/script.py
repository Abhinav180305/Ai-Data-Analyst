
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\da86a7bd-3bd5-44ad-b7d4-ead83142a9ef\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\da86a7bd-3bd5-44ad-b7d4-ead83142a9ef")

s = df['PoolQC'].fillna('Missing')
counts = s.value_counts()
counts.plot.pie(autopct='%1.1f%%')
plt.ylabel('')
plt.title('PoolQC distribution')
plt.tight_layout()
plt.savefig('chart.png')
result = counts

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
