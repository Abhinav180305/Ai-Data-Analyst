
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\10b41bf2-388e-4181-b789-75c6e9663a0d\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\10b41bf2-388e-4181-b789-75c6e9663a0d")

# Split cuisine strings, explode to one row per cuisine and count frequencies
cuisine_counts = df['cuisine'].str.split(r',\s*').explode().value_counts()
result = cuisine_counts
# Plot the top 10 cuisines as a pie chart and save to chart.png
top = cuisine_counts.head(10)
fig, ax = plt.subplots()
top.plot.pie(ax=ax, autopct='%1.1f%%', startangle=90, ylabel='')
ax.set_title('Top 10 Cuisine Distribution')
fig.tight_layout()
fig.savefig('chart.png')
plt.close(fig)

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
