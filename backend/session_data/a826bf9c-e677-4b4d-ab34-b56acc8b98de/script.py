
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\a826bf9c-e677-4b4d-ab34-b56acc8b98de\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\a826bf9c-e677-4b4d-ab34-b56acc8b98de")

import matplotlib.pyplot as plt
age_counts = df['age'].value_counts()
age_counts.plot.pie(ax=plt.gca(), autopct='%1.1f%%')
plt.ylabel('')
plt.title('Age Distribution')
plt.savefig('chart.png')
result = age_counts

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
