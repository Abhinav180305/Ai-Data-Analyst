
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\82431671-0f9e-44f6-93ec-4e0755ce4433\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\82431671-0f9e-44f6-93ec-4e0755ce4433")

result = df['SepalLengthCm'].value_counts().sort_index()
plt.figure(figsize=(6,6))
result.plot.pie(autopct='%1.1f%%')
plt.ylabel('')
plt.title('Distribution of Sepal Length (cm)')
plt.savefig('chart.png')
plt.close()

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
