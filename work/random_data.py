import pandas as pd
from pathlib import Path


PROJECT_ROOT=Path(__file__).resolve().parents[1]
DEFAULT_INPUT=PROJECT_ROOT/"data"/"UserBehavior.csv"
DEFAULT_OUTPUT=PROJECT_ROOT/"data"/"sample_100k.csv"

Target=100_000
columns=["user_id","item_id","category_id","behavior_type","timestamp"]
CHUNK_SIZE=5_000_000

def sample_csv(n:int =Target)->pd.DataFrame:
    reader=pd.read_csv(DEFAULT_INPUT,header=None,names=columns,chunksize=CHUNK_SIZE)

    chunks=list(reader)
    n_chunks=len(chunks)
    per_chunk=max(n//n_chunks,1)

    samples = [chunk.sample(n=min(per_chunk, len(chunk))) for chunk in chunks]
    df=pd.concat(samples,ignore_index=True).sample(frac=1)#打乱

    print(f"共{n_chunks}块,每块抽{per_chunk}行,实际抽样{len(df)}行")
    return df

if __name__ == "__main__":
    sample_csv().to_csv(DEFAULT_OUTPUT, index=False)
    print(f"输出文件:{DEFAULT_OUTPUT}")