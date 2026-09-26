
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\b5374680-1210-41aa-821b-483a46c339d2\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\b5374680-1210-41aa-821b-483a46c339d2")

import matplotlib.pyplot as plt
counts = df['YearBuilt'].value_counts().sort_index()
top_counts = counts.nlargest(10)
plt.figure(figsize=(6,6))
top_counts.plot.pie(autopct='%1.1f%%', startangle=90)
plt.ylabel('')
plt.title('Top 10 YearBuilt distribution')
plt.tight_layout()
plt.savefig('chart.png')
result = top_counts

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
