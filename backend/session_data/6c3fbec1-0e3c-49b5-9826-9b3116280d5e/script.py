
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\6c3fbec1-0e3c-49b5-9826-9b3116280d5e\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\6c3fbec1-0e3c-49b5-9826-9b3116280d5e")

# compute R&D spend per state
state_totals = df.groupby('State')['R&D Spend'].sum()
result = state_totals
# plot pie chart
plt.figure(figsize=(6,6))
state_totals.plot.pie(autopct='%1.1f%%')
plt.title('R&D Spend Distribution by State')
plt.ylabel('')
plt.savefig('chart.png')
plt.close()

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
