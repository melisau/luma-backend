import argparse, os, subprocess
parser=argparse.ArgumentParser();parser.add_argument("backup");parser.add_argument("--confirm",action="store_true");args=parser.parse_args()
if not args.confirm: raise SystemExit("Geri yüklemek için --confirm gerekli")
url=os.environ.get("DATABASE_URL")
if not url or not url.startswith("postgresql"): raise SystemExit("DATABASE_URL PostgreSQL olmalı")
subprocess.run(["pg_restore","--clean","--if-exists","--no-owner","--dbname",url.replace("postgresql+psycopg2://","postgresql://"),args.backup],check=True)
