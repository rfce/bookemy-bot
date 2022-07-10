import os
import psycopg2

database_url = os.environ.get("DATABASE_URL")

connection = psycopg2.connect(database_url)
cur = connection.cursor()

## Create database

init_data = """CREATE TABLE users (user_id varchar(32), num_searches varchar(32), last_message varchar(32), user_sites varchar(32), page_num varchar(32), member_type varchar(32), date varchar(32), info varchar(32));"""
cur.execute(init_data)

connection.commit()

connection.close()

print('table users created successfully!')
