import argparse, os, subprocess
parser=argparse.ArgumentParser();parser.add_argument("output");args=parser.parse_args()
url=os.environ.get("DATABASE_URL")
if not url or not url.startswith("postgresql"): raise SystemExit("DATABASE_URL PostgreSQL olmalı")
subprocess.run(["pg_dump","--format=custom","--file",args.output,url.replace("postgresql+psycopg2://","postgresql://")],check=True)
