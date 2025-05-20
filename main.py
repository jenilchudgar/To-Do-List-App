from flask import Flask,request,render_template,redirect,url_for,abort
from flask_mysqldb import MySQL
from flask_login import LoginManager,UserMixin,login_user,login_required,logout_user,current_user
from flask_bcrypt import Bcrypt
from datetime import datetime,date as dt
import MySQLdb.cursors
from base64 import *

app = Flask(__name__)
app.secret_key = 'SECRET_KEY_2025'
app.url_map.strict_slashes = False

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
        cursor.execute("SELECT * FROM persons WHERE id = %s",(user_id,))
        acc = cursor.fetchone()
        if acc:
            return User(id=acc['id'],username=acc['username'],role=acc['role'])
        return None

def is_admin():
    try:
        admin = current_user.is_authenticated and current_user.role == "admin"
    except:
        admin = False
    return admin

@app.errorhandler(401)
def unauthorized_error(error):
    return render_template("result.html",title="Unauthorized Access!",msg="Kindly login or contact your administrator.",color="#fc4747",image="error.png",rd="home"),401 

@app.errorhandler(404)
def not_found_error(error):
    return render_template("result.html",title="File or Path Not Found!",msg="The thing you asked for is not available. Try again later.",color="#fc4747",image="error.png",rd="home"),404

@login_required
@app.route('/view_user_tasks/<int:user_id>',methods=['GET'])
def view_user_tasks(user_id):
    if is_admin():
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM tasks WHERE user_id = %s",(user_id,))
        tasks = cursor.fetchall()
        
        cursor.execute("SELECT * FROM persons WHERE id = %s",(user_id,))
        user = cursor.fetchone()
        if user:
            li,title, status_code = get_tasks(tasks,title=f"Task(s) for {user['username']}")
            
            if status_code == 200:
                return render_template("tasks.html",full_list=li,title=title),status_code
        
        return render_template("result.html",title="No Tasks Currently!",msg="The following user currently has no tasks assigned to him. Click okay to add a task for them.",color="#fc4747",image="error.png",rd="add_task"),404

    return abort(401)

@app.route('/logout')
@login_required
def logout():
    logout_user() 
    return render_template("result.html",title="Logout Successful!",msg="We're sorry to see you go, do return later to complete your tasks!",color="#67ffa1",image="tick.png",rd="home"),200

@app.route('/tasks',methods=['GET'])
@login_required
def view_task():
    user_id = current_user.id
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if is_admin():
        cursor.execute("SELECT * FROM tasks")
        title = "All Tasks"
    else:
        cursor.execute("SELECT * FROM tasks WHERE user_id = %s",(user_id,))     
        title = "Your Tasks"   

    tasks = cursor.fetchall()
    li,title,status_code = get_tasks(tasks,title)

    if status_code == 200:
        return render_template("tasks.html",title=title,full_list=li,),status_code
    else:
        title = "Currently you have no Tasks"
    return render_template("tasks.html",title=title),status_code

def get_tasks(tasks,title):
    user = current_user
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    users = []
    l = []

    base64_images = []
    for img in tasks:
        if img['image'] is not None:
            base64_img = b64encode(img['image']).decode('utf-8')
        else:
            base64_img = ""
        base64_images.append(base64_img)

    if not tasks:
        li = []
        title = "No Task Assigned Currently!"
        status_code = 404
        return (title,li,status_code)
    
    else:
        assigned_by_list = []
        for task in tasks:
            cursor.execute("SELECT * FROM persons where id = %s",(task['assigned_by'],))
            assigned_by_list.append(cursor.fetchone())

        if is_admin():
            for task in tasks:
                cursor.execute("SELECT * FROM persons WHERE id = %s",(task['user_id'],))
                user = cursor.fetchone()
                users.append(user)

            for user,task,img,assigned in zip(users,tasks,base64_images,assigned_by_list):
                if user['username'] is not None:
                    l.append((user['username'],task,img,assigned))
                else:
                    l.append(("Deleted User",task,img,assigned))
        else:
            now = datetime.now()
            date_list = []
            for task,img,assigned in zip(tasks,base64_images,assigned_by_list):
                date_list = str(task['start_date']).split("-")
                if task['status'] == "Pending" and int(date_list[0]) == now.year and int(date_list[1]) == now.month and int(date_list[2]) <= now.day:
                    l.append((user.username,task,img,assigned))

        status_code = 200
        if not l:
            status_code = 404
        return (l,title,status_code)

@app.route('/add_task/',methods=['GET','POST'])
@login_required
def add_task():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if "task" in request.form and request.method == 'POST':
        task = request.form['task']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        date = dt.today()
        time = datetime.now()
        currentdt = f"{date} {time.hour}:{time.minute}:{time.second}"

        image = request.files['image']
        image_data = None

        if image:
            image_data = image.read()

        if is_admin():
            user_id = int(request.form['userid'])
        else:
            user_id = current_user.id
        
        assigned_by = current_user.id

        # Status must be pending by default
        status = "Pending"

        cursor.execute("INSERT INTO tasks (user_id, task,image,start_date,end_date,currentdt,assigned_by,status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (user_id,task,image_data,start_date,end_date,currentdt,assigned_by,status)
        )
        mysql.connection.commit()
        
        if is_admin():
            cursor.execute("SELECT * FROM tasks")
            title = "All Tasks"
        else:
            cursor.execute("SELECT * FROM tasks WHERE user_id = %s",(user_id,))     
            title = "Your Tasks"   

        tasks = cursor.fetchall()
        li,title,status_code = get_tasks(tasks,title)

        if status_code == 200:
            return render_template("tasks.html",title=title,full_list=li,),status_code
        else:
            title = "Currently you have no Tasks"
            
        return render_template("tasks.html",title=title),status_code
    
    cursor.execute("SELECT * FROM persons")
    users = cursor.fetchall()
    return render_template("add_tasks.html",admin=is_admin(),users=users),200

@app.route('/delete_task/<int:task_id>',methods=['GET','POST'])
@login_required
def delete_task(task_id):
    user_id = current_user.id
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if is_admin():
        cursor.execute("DELETE FROM TASKS WHERE id = %s",(task_id,))
    else:
        cursor.execute("DELETE FROM TASKS WHERE id = %s and user_id = %s",(task_id,current_user.id))

    mysql.connection.commit()
    
    if is_admin():
        cursor.execute("SELECT * FROM tasks")
        title = "All Tasks"
    else:
        cursor.execute("SELECT * FROM tasks WHERE user_id = %s",(user_id,))     
        title = "Your Tasks"   

    tasks = cursor.fetchall()
    li,title,status_code = get_tasks(tasks,title)

    if status_code == 200:
        return render_template("tasks.html",title=title,full_list=li,),status_code
    else:
        title = "Currently you have no Tasks"
    return render_template("tasks.html",title=title),status_code

@app.route('/update_task/<int:task_id>',methods=['GET','POST'])
@login_required
def update_task(task_id):
    user_id = current_user.id
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if "image" in request.files:
        img = request.files['image'].read()
    
    if request.method == 'POST':
        if is_admin():
            if img:
                cursor.execute("UPDATE TASKS SET task = %s, image = %s WHERE id = %s",(request.form['task'],img, task_id))
            else:
                cursor.execute("UPDATE TASKS SET task = %s WHERE id = %s",(request.form['task'], task_id))
        else:
            if img:
                cursor.execute("UPDATE TASKS SET task = %s, image = %s WHERE id = %s AND user_id = %s",(request.form['task'],img, task_id, current_user.id))
            else:
                cursor.execute("UPDATE TASKS SET task = %s WHERE id = %s AND user_id = %s",(request.form['task'], task_id, current_user.id))

        mysql.connection.commit()
        
        if is_admin():
            cursor.execute("SELECT * FROM tasks")
            title = "All Tasks"
        else:
            cursor.execute("SELECT * FROM tasks WHERE user_id = %s",(user_id,))     
            title = "Your Tasks"   

        tasks = cursor.fetchall()
        li,title,status_code = get_tasks(tasks,title)

        if status_code == 200:
            return render_template("tasks.html",title=title,full_list=li,),status_code
        else:
            title = "Currently you have no Tasks"
        return render_template("tasks.html",title=title),status_code
    
    
    if is_admin():
        cursor.execute("SELECT * FROM TASKS WHERE id = %s",(task_id,))
    else:
        cursor.execute("SELECT * FROM TASKS WHERE user_id = %s and id = %s",(current_user.id,task_id))

    task = cursor.fetchone()
    return render_template('update_task.html',task_id=task_id,task=task),200

@app.route('/',methods=['GET'])
def home():
    is_user = current_user.is_authenticated
    return render_template("index.html",is_user=is_user,admin=is_admin(),user=current_user)

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

        cursor.execute("SELECT * FROM persons WHERE USERNAME = %s",(username,))
        acc = cursor.fetchone()
        if acc:
            is_valid = bcrypt.check_password_hash(acc['password'], password)
            if is_valid:
                title = "Login Successful!"
                msg = "You have successfully logged into your website. Enjoy the experience and do your tasks deligently."
                rd = "home"
                img = "tick.png"
                color = "#67ffa1"
                code = 200
                user = User(id=acc['id'],username=acc['username'],role=acc['role'])

                login_user(user,remember=('check' in request.form))
            else:
                title = "Login Failed!"
                msg = "The Login Failed as you entered the incorrect password. Kindly retry."
                rd = "login"
                img = "error.png"
                color = "#fc4747"
                code = 400
        else:
            title = "Your Account doesn't exist!"
            msg = "The Login Failed as your account doesn't exist in our database. Kindly register first."
            rd = "login"
            img = "error.png"
            color = "#fc4747"
            code = 400
        
        return render_template("result.html",title=title,msg=msg,rd=rd,image=img,color=color),code
    return render_template("login.html")

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method == "POST" and "username" in request.form and "password" in request.form:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        username = request.form['username']
        password = request.form['password']
        city = request.form['city']
        role = "user"
        cursor.execute("SELECT * FROM persons WHERE USERNAME = %s",(username, ))
        acc = cursor.fetchone()

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        if acc:
            title = "Account already Exists!" 
            code = 400
        else:
            cursor.execute("INSERT INTO persons (username, password, city,role) VALUES (%s, %s, %s,%s)",(username,hashed_password,city,role))
            title = "You have successfully registered!"
            code = 200
        mysql.connection.commit()
        
        return render_template("result.html",title=title,msg="Thank you for registering on our websites. Enjoy the website experience!",color="#fccc47",image="tick.png",rd="login"),code
    
    return render_template("register.html")

@login_required
@app.route('/users',methods=['GET'])
def view_users():
    if is_admin():
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM persons")
        users = cursor.fetchall()
        return render_template("users.html",admin=is_admin(),users=users),200
    else:
        return render_template("result.html",title="Unauthorized Access!",msg="The following site can only be accessed by an admin. Contact your administrator for more information.",color="#fc4747",image="error.png",rd="home"),401

@login_required
@app.route('/change_role/<int:user_id>',methods=['GET','POST'])
def change_role(user_id):
    if is_admin():
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
        cursor.execute("SELECT * FROM persons WHERE id = %s",(user_id,))
        user = cursor.fetchone()

        if user['role'] == "admin":
            role = "user"
        else:
            role = "admin"

        cursor.execute("UPDATE persons SET role = %s WHERE id = %s",(role,user_id,))
        mysql.connection.commit()
        return redirect(url_for('view_users'))
    
    return render_template("result.html",title="Unauthorized Access!",msg="The following site can only be accessed by an admin. Contact your administrator for more information.",color="#fc4747",image="error.png",rd="home"),401

@login_required
@app.route('/delete_user/<int:user_id>',methods=['GET','POST'])
def delete_user(user_id):
    if is_admin():
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("DELETE FROM persons WHERE id =  %s",(user_id,))
        cursor.execute("DELETE FROM tasks WHERE user_id = %s",(user_id,))

        mysql.connection.commit()
        return redirect(url_for('view_users')),200

    return render_template("result.html",title="Unauthorized Access!",msg="The following site can only be accessed by an admin. Contact your administrator for more information.",color="#fc4747",image="error.png",rd="home"),401

@login_required
@app.route('/search',methods=['GET','POST'])
def search():
    if request.method == "POST" and "search_box" in request.form:
        q = request.form['search_box']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        pattern = f"%{q}%"
        if is_admin():  
            cursor.execute("SELECT * FROM tasks WHERE task LIKE %s" ,(pattern,))
        else:
            cursor.execute("SELECT * FROM tasks WHERE task LIKE %s AND user_id = %s",(pattern,current_user.id))

        tasks = cursor.fetchall()
        if is_admin():
            title = f'Search Results for "{q}" from all users'
        else:
            title = f'Search Results for "{q}"'

        li,title,status_code = get_tasks(tasks,title)
        print(li,title,status_code)
        if status_code == 200:
            return render_template("tasks.html",title=title,full_list=li),status_code
        else:
            abort(404)

    return render_template("index.html"),400

@login_required
@app.route('/mark_complete/<int:task_id>')
def mark_complete(task_id):
    if is_admin():
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("UPDATE tasks SET status = %s WHERE id = %s",("Complete",task_id))
        mysql.connection.commit()

        cursor.execute("SELECT * FROM tasks")
        tasks = cursor.fetchall()
        li,title,status_code = get_tasks(tasks=tasks,title=f"Task {task_id} marked Complete!")
        
        if status_code == 200:
            return render_template("tasks.html",title=title,full_list=li),status_code
        else:
            abort(404)
    else:
        abort(401)

@login_required
@app.route('/reassign/',methods=['GET','POST'])
def reassign():
    ci = current_user.id
    if is_admin() and request.method == "POST":
        user_id = request.form['userid']
        task_id = request.form['task_id']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("UPDATE tasks SET user_id = %s, ASSIGNED_BY = %s  WHERE id = %s",(user_id,current_user.id,task_id))
        mysql.connection.commit()

        cursor.execute("SELECT * FROM persons WHERE id = %s",(user_id,))
        username = cursor.fetchone()

        if is_admin():
            cursor.execute("SELECT * FROM tasks")
            title = f"Task {task_id} reassigned to {username['username']}" 

            tasks = cursor.fetchall()
            li,title,status_code = get_tasks(tasks,title)

            if status_code == 200:
                return render_template("tasks.html",title=title,full_list=li,),status_code
            else:
                title = "Currently you have no Tasks"
            return render_template("tasks.html",title=title),status_code
        
    return abort(401)

@login_required
@app.route('/reassign_task/<int:task_id>')
def reassign_task(task_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM persons")
    users = cursor.fetchall()
    return render_template("reassign.html",title="Select the user who you want to reassign the task to",users=users,task_id=task_id)

if __name__ == '__main__':
    app.run(debug=True) 