
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\a24a89ea-1e46-456f-b0ef-eb135d83e9ba\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\a24a89ea-1e46-456f-b0ef-eb135d83e9ba")

import matplotlib.pyplot as plt
# Count smokers vs non-smokers
result = df['smoker'].value_counts().rename({False:'Non-smoker',True:'Smoker'})
# Plot pie chart
plt.figure(figsize=(6,6))
plt.pie(result, labels=result.index, autopct='%1.1f%%', startangle=90, colors=['#66b3ff','#ff9999'])
plt.title('Smoker Distribution')
plt.savefig('chart.png', bbox_inches='tight')
plt.close()

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
