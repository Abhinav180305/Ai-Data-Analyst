
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\22b09866-c9ed-4df6-8fdc-08861a829758\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\22b09866-c9ed-4df6-8fdc-08861a829758")

import matplotlib.pyplot as plt
counts=df['PoolQC'].value_counts(dropna=False)
counts.index=counts.index.map(lambda x: str(x) if pd.notnull(x) else 'Missing')
fig,ax=plt.subplots()
ax.pie(counts,labels=counts.index,autopct='%1.1f%%',startangle=90)
ax.axis('equal')
plt.tight_layout()
plt.savefig('chart.png')
result=counts

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
