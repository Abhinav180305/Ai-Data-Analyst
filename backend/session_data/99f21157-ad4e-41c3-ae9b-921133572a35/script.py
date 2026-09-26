
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\99f21157-ad4e-41c3-ae9b-921133572a35\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\99f21157-ad4e-41c3-ae9b-921133572a35")

import matplotlib.pyplot as plt
city_counts = df['city'].value_counts()
result = city_counts
fig, ax = plt.subplots()
city_counts.plot.pie(ax=ax, autopct='%1.1f%%', startangle=90, counterclock=False)
ax.set_ylabel('')
plt.title('Distribution of Cities')
plt.tight_layout()
plt.savefig('chart.png')
plt.close(fig)

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
