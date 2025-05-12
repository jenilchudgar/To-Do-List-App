from flask import Flask,request,render_template,redirect,url_for,abort
from flask_mysqldb import MySQL
from flask_login import LoginManager,UserMixin,login_user,login_required,logout_user,current_user
from flask_bcrypt import Bcrypt
import MySQLdb.cursors

app = Flask(__name__)
app.secret_key = 'SECRET_KEY_2025'

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)

# Bcrypt Password Protection
bcrypt = Bcrypt(app)

# MySQL Database Declarations
app.config['MYSQL_PORT'] = 3306
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'jenil1234'
app.config['MYSQL_DB'] = 'FLASKBASE'

mysql = MySQL(app)
class User(UserMixin):
    def __init__(self,id,username,role):
        self.id = id
        self.username = username
        self.role = role
    
    @staticmethod
    def get(user_id):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM Persons WHERE id = %s",(user_id,))
        acc = cursor.fetchone()
        if acc:
            return User(id=acc['id'],username=acc['username'],role=acc['role'])
        return None

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return render_template("result.html",msg="Logout Successful!")

@app.route('/tasks',methods=['GET'])
@login_required
def view_task():
    admin = current_user.role == "admin"
    user_id = current_user.id
    user = current_user.username
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM tasks WHERE user_id = %s",(user_id,))
    if admin:
        cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()
    users = []
    l = []
    if admin:
        for task in tasks:
            cursor.execute("SELECT * FROM persons WHERE id = %s",(task['user_id'],))
            user = cursor.fetchone()
            users.append(user)
        print(users)
        for user,task in zip(users,tasks):
            if user['username'] is not None:
                l.append((user['username'],task,))
            else:
                l.append(("Deleted User",task,))
    else:
        for task in tasks:
            l.append((user,task,))
    
    return render_template("tasks.html",full_list=l)

@app.route('/add_task/',methods=['GET','POST'])
@login_required
def add_task():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    admin = current_user.role == "admin"
    if "task" in request.form and "time" in request.form and request.method == 'POST':
        task = request.form['task']
        time = request.form['time']
        user_id = current_user.id
        if admin:
            user_id = request.form['userid']
            print(user_id)
        
        cursor.execute("INSERT INTO Tasks (user_id, time, task) VALUES (%s, %s, %s)",(user_id,time,task))
        mysql.connection.commit()
        return redirect(url_for('view_task'))  
    admin = current_user.role == "admin"
    cursor.execute("SELECT * FROM Persons")
    users = cursor.fetchall()
    return render_template("add_tasks.html",admin=admin,users=users)

@app.route('/delete_task/<int:task_id>',methods=['GET','POST'])
@login_required
def delete_task(task_id):
    admin = current_user.role == "admin"
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("DELETE FROM TASKS WHERE id = %s and user_id = %s",(task_id,current_user.id))
    if admin:
        cursor.execute("DELETE FROM TASKS WHERE id = %s",(task_id,))
    mysql.connection.commit()
    return redirect(url_for('view_task'))

@app.route('/update_task/<int:task_id>',methods=['GET','POST'])
@login_required
def update_task(task_id):
    admin = current_user.role == "admin"
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if request.method == 'POST':
        cursor.execute("UPDATE TASKS SET time = %s, task = %s WHERE id = %s AND user_id = %s",(request.form['time'], request.form['task'], task_id, current_user.id))

        if admin:
            cursor.execute("UPDATE TASKS SET time = %s, task = %s WHERE id = %s",(request.form['time'], request.form['task'], task_id))
        
        mysql.connection.commit()
        return redirect(url_for('view_task'))
    
    cursor.execute("SELECT * FROM TASKS WHERE user_id = %s and id = %s",(current_user.id,task_id))
    if admin:
        cursor.execute("SELECT * FROM TASKS WHERE id = %s",(task_id,))
    task = cursor.fetchone()
    return render_template('update_task.html',task_id=task_id,task=task)

@app.route('/',methods=['GET'])
def home():
    is_user = current_user.is_authenticated
    try:
        admin = current_user.role == "admin"
    except:
        admin = False
    return render_template("index.html",is_user=is_user,admin=admin,user=current_user)

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.route('/login',methods=['POST','GET'])
def login():
    if request.method == "POST" and 'username' in request.form and 'password' in request.form:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        username = request.form['username']
        password = request.form['password']
        msg=""

        cursor.execute("SELECT * FROM Persons WHERE USERNAME = %s",(username,))
        acc = cursor.fetchone()
        if acc:
            is_valid = bcrypt.check_password_hash(acc['password'], password)
            if is_valid:
                msg = "Login Successful!"
                user = User(id=acc['id'],username=acc['username'],role=acc['role'])

                login_user(user,remember=('check' in request.form))
            else:
                msg = "Login Failed! (Pehle password yaad kar ke aa!)"
            return render_template("result.html",msg=msg)
        else:
            msg = "Your Account doesnt exist! Kindly register first!"
        mysql.connection.commit()
    return render_template("login.html")

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method == "POST" and "username" in request.form and "password" in request.form:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        username = request.form['username']
        password = request.form['password']
        city = request.form['city']
        role = "user"
        cursor.execute("SELECT * FROM Persons WHERE USERNAME = %s",(username, ))
        acc = cursor.fetchone()

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        if acc:
            msg = "Account already Exists!" 
        else:
            cursor.execute("INSERT INTO Persons (username, password, city,role) VALUES (%s, %s, %s,%s)",(username,hashed_password,city,role))
            msg = "You have successfully registered!"
        mysql.connection.commit()
        
        return render_template("result.html",msg=msg)
    
    return render_template("register.html")

@login_required
@app.route('/users',methods=['GET'])
def view_users():
    admin = current_user.role == "admin"
    if admin:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM Persons")
        users = cursor.fetchall()
        return render_template("users.html",admin=admin,users=users)
    else:
        return abort(401)

@login_required
@app.route('/change_role/<int:user_id>',methods=['GET','POST'])
def change_role(user_id):
    admin = current_user.role == "admin"
    if admin:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
        cursor.execute("SELECT * FROM Persons WHERE id = %s",(user_id,))
        user = cursor.fetchone()

        if user['role'] == "admin":
            role = "user"
        else:
            role = "admin"

        cursor.execute("UPDATE persons SET role = %s WHERE id = %s",(role,user_id,))
        mysql.connection.commit()
        return redirect(url_for('view_users'))
    return abort(401)

@login_required
@app.route('/delete_user/<int:user_id>',methods=['GET','POST'])
def delete_user(user_id):
    admin = current_user.role == "admin"
    if admin:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("DELETE FROM Persons WHERE id =  %s",(user_id,))
        cursor.execute("DELETE FROM Tasks WHERE user_id = %s",(user_id,))

        mysql.connection.commit()
        return redirect(url_for('view_users'))

    return abort(401)

if __name__ == '__main__':
    app.run(debug=True)