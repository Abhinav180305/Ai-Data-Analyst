
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\72914fc8-1033-4805-9aa6-02a6def78711\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\72914fc8-1033-4805-9aa6-02a6def78711")

import matplotlib.pyplot as plt
counts = df['YearBuilt'].value_counts().sort_index()
fig, ax = plt.subplots()
counts.plot.pie(ax=ax, autopct='%1.1f%%', startangle=90)
ax.set_ylabel('')
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
