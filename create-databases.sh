set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    CREATE DATABASE oltp;
    CREATE DATABASE olap;
    GRANT ALL PRIVILEGES ON DATABASE oltp TO postgres;
    GRANT ALL PRIVILEGES ON DATABASE olap TO postgres;
EOSQL
