from flask_login import UserMixin
from app import mysql
import MySQLdb.cursors

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

    @staticmethod
    def get(user_id):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        acc = cursor.fetchone()
        if acc:
            return User(id=acc['id'], username=acc['username'], role=acc['role'])
        return None
