
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\95f99a62-9278-4e41-8a2d-d56c6e7e773b\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\95f99a62-9278-4e41-8a2d-d56c6e7e773b")

import matplotlib.pyplot as plt
cuisine_counts = df['cuisine'].str.split(',\s*').explode().str.strip().value_counts()
# Aggregate less frequent cuisines into 'Other' for a clearer pie chart
N = 10
if len(cuisine_counts) > N:
    top = cuisine_counts.head(N)
    other = cuisine_counts.iloc[N:].sum()
    top['Other'] = other
    plot_data = top
else:
    plot_data = cuisine_counts
plt.figure(figsize=(8,8))
plot_data.plot.pie(autopct='%1.1f%%', startangle=140)
plt.ylabel('')
plt.title('Cuisine Distribution')
plt.tight_layout()
plt.savefig('chart.png')
plt.close()
result = cuisine_counts

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
