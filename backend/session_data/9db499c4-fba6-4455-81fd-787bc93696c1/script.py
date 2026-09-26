
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\9db499c4-fba6-4455-81fd-787bc93696c1\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\9db499c4-fba6-4455-81fd-787bc93696c1")

counts = df['YearBuilt'].value_counts().sort_index(); counts.plot.pie(figsize=(8,8), autopct='%1.1f%%'); plt.ylabel(''); plt.title('Distribution of YearBuilt'); plt.tight_layout(); plt.savefig('chart.png'); result = counts

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
