import psycopg2
conn = psycopg2.connect(
    host='aws-1-ap-southeast-1.pooler.supabase.com',
    user='postgres.awjjkshfyxwahoooiqnl',
    password='AaryaButolia1109',
    dbname='postgres',
    port=5432,
    sslmode='require'
)
print('Connected!', conn.status)
conn.close()