import pandas as pd

if __name__ == '__main__':
    ds = pd.read_csv("./output/csv/tickets_prs_merged.csv")
    for col in ds.columns:
        print(col)
