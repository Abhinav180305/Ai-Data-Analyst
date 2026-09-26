
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\f4867828-54f5-4cce-9c1a-76a7b4e6fc63\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\f4867828-54f5-4cce-9c1a-76a7b4e6fc63")

age_counts = df['age'].value_counts(); result = age_counts; plt.figure(figsize=(8,8)); age_counts.plot.pie(autopct='%1.1f%%', startangle=90); plt.ylabel(''); plt.title('Age Distribution'); plt.tight_layout(); plt.savefig('chart.png');

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
