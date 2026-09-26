
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\27d16b89-a095-4d15-a684-995789c9970d\data.pkl")
os.chdir(r"C:\Users\jhaab\Downloads\ai-data-analyst\ai-data-analyst\backend\session_data\27d16b89-a095-4d15-a684-995789c9970d")

import pandas as pd, matplotlib.pyplot as plt
bins=[df['GrLivArea'].min(),1500,2500,df['GrLivArea'].max()]
labels=['Low','Medium','High']
result=pd.cut(df['GrLivArea'],bins=bins,labels=labels,include_lowest=True).value_counts().sort_index()
result.plot.pie(autopct='%1.1f%%')
plt.ylabel('')
plt.title('GrLivArea distribution')
plt.savefig('chart.png')


out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
