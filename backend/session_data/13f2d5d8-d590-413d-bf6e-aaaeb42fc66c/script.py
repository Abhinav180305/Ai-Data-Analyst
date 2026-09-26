
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\13f2d5d8-d590-413d-bf6e-aaaeb42fc66c\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\13f2d5d8-d590-413d-bf6e-aaaeb42fc66c")

import pandas as pd
import matplotlib.pyplot as plt
# Count occurrences of each category in column '1'
result = df['1'].value_counts()
# Plot pie chart and save to file
plt.figure()
result.plot.pie(autopct='%1.1f%%')
plt.title('Distribution of column 1')
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
