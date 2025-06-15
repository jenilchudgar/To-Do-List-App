from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app import mysql
from flask import abort
from datetime import datetime,date as dt
from app.utils import *
from app.constants import *
from flask_mysqldb import MySQLdb
from base64 import *

bp = Blueprint('tasks', __name__)

@bp.route('/tasks')
@login_required
def view_tasks():
    sort_by = request.args.get("sort_by")
    if sort_by:
        tasks = order(sort_by)
        title = f"Entries sorted by \"{sort_by.replace('_',' ').capitalize()}\""
        li,title,status_code = get_tasks(tasks,title)

        return render_template("tasks.html",title=title,full_list=li,),status_code

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

@bp.route('/view_user_tasks/<int:user_id>',methods=['GET'])
@login_required
def view_user_tasks(user_id):
    if is_admin():
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM tasks WHERE user_id = %s",(user_id,))
        tasks = cursor.fetchall()
        
        cursor.execute("SELECT * FROM users WHERE id = %s",(user_id,))
        user = cursor.fetchone()
        if user:
            li,title, status_code = get_tasks(tasks,title=f"Task(s) for {user['username']}")
            
            if status_code == 200:
                return render_template("tasks.html",full_list=li,title=title),status_code
        
        return render_template("result.html",title="No Tasks Currently!",msg="The following user currently has no tasks assigned to him. Click okay to add a task for them.",color=RED,image=ERROR,rd="add_task"),404

    return abort(401)

def order(sort_by):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    valid_sorts = {
        "id":"id ASC",
        "assigned_to":"assigned_to.username ASC",
        "assigned_by":"assigned_by.username ASC",
        "status":"status = 'Pending' DESC, id ASC",
        "start_date":"start_date ASC",
        "end_date":"end_date ASC",
        "Creation_DT":"currentdt ASC",
        "priority": "FIELD(priority, 'Urgent', 'Important', 'Least Important') ASC"
    }

    query = """
        SELECT t.*, assigned_to.username AS assigned_to_name, assigned_by.username AS assigned_by_name
        FROM tasks t
        JOIN users assigned_to ON t.user_id = assigned_to.id
        JOIN users assigned_by ON t.assigned_by = assigned_by.id
    """
    params = []

    if not is_admin():
        query += "WHERE user_id = %s"
        params.append(current_user.id)

    query += f" ORDER BY {valid_sorts.get(sort_by).replace("_"," ")}"
    
    cursor.execute(query,params)
    tasks = cursor.fetchall()
    return tasks

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
            cursor.execute("SELECT * FROM users where id = %s",(task['assigned_by'],))
            assigned_by_list.append(cursor.fetchone())

        if is_admin():
            for task in tasks:
                cursor.execute("SELECT * FROM users WHERE id = %s",(task['user_id'],))
                user = cursor.fetchone()
                users.append(user)

            for user,task,img,assigned in zip(users,tasks,base64_images,assigned_by_list):
                if user['username'] is not None:
                    l.append((f"{user['first_name']} {user['last_name']}",task,img,assigned))
                else:
                    l.append(("Deleted User",task,img,assigned))
        else:
            now = datetime.now()
            date_list = []
            cursor.execute("SELECT * FROM users WHERE id = %s",(current_user.id,))
            user = cursor.fetchone()

            for task,img,assigned in zip(tasks,base64_images,assigned_by_list):
                date_list = str(task['start_date']).split("-")

                if task['status'] == "Pending" and int(date_list[0]) == now.year and int(date_list[1]) == now.month and int(date_list[2]) <= now.day:
                    l.append((f"{user['first_name']} {user['last_name']}",task,img,assigned))

        status_code = 200
        if not l:
            status_code = 404
        return (l,title,status_code)

@bp.route('/add_task/',methods=['GET','POST'])
@login_required
def add_task():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if "task" in request.form and request.method == 'POST':
        task = request.form['task']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        priotity = request.form['priotity']

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

        status = "Pending"

        cursor.execute("INSERT INTO tasks (user_id, task,image,start_date,end_date,currentdt,assigned_by,status,priority) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (user_id,task,image_data,start_date,end_date,currentdt,assigned_by,status,priotity)
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
    
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    return render_template("add_tasks.html",admin=is_admin(),users=users,priority=["Urgent","Important","Least Important"]),200

@bp.route('/delete_task/<int:task_id>',methods=['GET','POST'])
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

@bp.route('/update_task/<int:task_id>',methods=['GET','POST'])
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

@bp.route('/mark_complete/<int:task_id>')
@login_required
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

## Reassigning Tasks
@bp.route('/reassign',methods=['GET','POST'])
@login_required
def reassign():
    if is_admin() and request.method == "POST":
        user_id = request.form['userid']
        task_id = request.form['task_id']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("UPDATE tasks SET user_id = %s, ASSIGNED_BY = %s  WHERE id = %s",(user_id,current_user.id,task_id))
        mysql.connection.commit()

        cursor.execute("SELECT * FROM users WHERE id = %s",(user_id,))
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

@bp.route('/reassign_task/<int:task_id>')
@login_required
def reassign_task(task_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    return render_template("reassign.html",title="Select the user who you want to reassign the task to",users=users,task_id=task_id)
