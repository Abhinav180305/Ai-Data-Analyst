
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\a0ccce2f-107d-4780-9547-6d5b2d261179\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\a0ccce2f-107d-4780-9547-6d5b2d261179")

top_cities = df['city'].value_counts().nlargest(10)
import matplotlib.pyplot as plt
plt.figure(figsize=(8,8))
top_cities.plot.pie(autopct='%1.1f%%')
plt.title('Top 10 Cities by Enrollee Count')
plt.ylabel('')
plt.savefig('chart.png')
result = top_cities

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
