import sqlite3, json
c = sqlite3.connect('rostering.db')
tables = list(c.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"))
user_info = list(c.execute("PRAGMA table_info('user')"))
print('tables:', json.dumps(tables, default=str))
print('user_info:', json.dumps(user_info, default=str))
