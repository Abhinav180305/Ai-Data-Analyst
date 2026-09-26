
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\18b89ea3-b488-4178-a808-9a35de93b995\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\18b89ea3-b488-4178-a808-9a35de93b995")

import matplotlib.pyplot as plt
counts = df['team1'].value_counts()
result = counts
counts.plot.pie(autopct='%1.1f%%', figsize=(8,8), title='Distribution of Team1')
plt.ylabel('')
plt.savefig('chart.png')

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
