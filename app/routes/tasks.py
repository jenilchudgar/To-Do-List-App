from flask import Blueprint, render_template, request,redirect,url_for
from flask_login import login_required, current_user
from app import mysql
from flask import abort
from datetime import datetime,date as dt
from app.utils import *
from app.constants import *
from flask_mysqldb import MySQLdb
from base64 import *
import json,random
from collections import defaultdict
from app.constants import comment_colors

bp = Blueprint('tasks', __name__)
   
def strip_images(li):
    safe = []

    for assigned_to, task, assigned_by in li:
        def clean_dict(d):
            new = {}
            for k, v in d.items():
                if isinstance(v, bytes):
                    continue  # REMOVE bytes completely
                elif isinstance(v, (dt, datetime)):
                    new[k] = v.isoformat()
                else:
                    new[k] = v
            return new

        task_clean = clean_dict(task)
        assigned_by_clean = clean_dict(assigned_by)

        safe.append([assigned_to, task_clean, assigned_by_clean])

    return safe

@bp.route('/tasks',methods=['GET','POST'])
@login_required
def tasks():
    if request.method == "POST":
        sort_by = request.form.get("sort_by")
        full_list_json = request.form.get("full_list_json")
        
        if full_list_json and sort_by:
            li = json.loads(full_list_json)

            def sort_key(entry):
                assigned_to, task, assigned_by = entry
                if sort_by == "id":
                    return task["id"]
                elif sort_by == "assigned_to":
                    return assigned_to.lower()
                elif sort_by == "assigned_by":
                    return f"{assigned_by['first_name']} {assigned_by['last_name']}".lower()
                elif sort_by == "start_date":
                    return task["start_date"]
                elif sort_by == "end_date":
                    return task["end_date"]
                elif sort_by == "priority":
                    return {"Urgent": 0, "Important": 1, "Least Important": 2}.get(task["priority"], 99)
                elif sort_by == "status":
                    return 0 if task["status"] == "Pending" else 1
                return 0

            li.sort(key=sort_key)
            title = f'Sorted by {sort_by.replace("_", " ").capitalize()}'
            return render_template("tasks.html", title=title, full_list=li, full_list_json=json.dumps(strip_images(li))), 200

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s",(current_user.id,))
    user = cursor.fetchone()
    sort_by = request.args.get("sort_by")

    if sort_by:
        if is_admin():
            tasks = order(sort_by)  # No user_id filter
        else:
            tasks = order(sort_by, user_id=current_user.id)

        title = f"Entries sorted by \"{sort_by.replace('_',' ').capitalize()}\""
        li,title,status_code = get_tasks(tasks,title)

        return render_template("tasks.html", title=title, full_list=li, full_list_json=json.dumps(strip_images(li))), 200

    user_id = current_user.id
    
    if is_admin():
        cursor.execute("SELECT * FROM tasks")
        title = "All Tasks"
    else:
        cursor.execute("SELECT * FROM tasks WHERE user_id = %s",(user_id,))     
        title = "Your Tasks"   

    tasks = cursor.fetchall()
    li,title,status_code = get_tasks(tasks,title)

    if status_code == 200:
        return render_template("tasks.html", title=title, full_list=li, full_list_json=json.dumps(strip_images(li))), 200
    else:
        title = "Currently you have no Tasks"
    return render_template("tasks.html", title=title, full_list=li, full_list_json=json.dumps(strip_images(li))), 200

@bp.route('/view_user_tasks/<int:user_id>',methods=['GET','POST'])
@login_required
def view_user_tasks(user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s",(user_id,))
    user = cursor.fetchone()
    sort_by = request.args.get("sort_by")
    if sort_by:
        tasks = order(sort_by, user_id=user_id)
        title = f"Entries sorted by \"{sort_by.replace('_',' ').capitalize()}\""
        li,title,status_code = get_tasks(tasks,title)

        return render_template("tasks.html", title=title, full_list=li, full_list_json=json.dumps(strip_images(li))), 200

    if is_admin():
        cursor.execute("SELECT * FROM tasks WHERE user_id = %s",(user_id,))
        tasks = cursor.fetchall()
        
        if user:
            li,title, status_code = get_tasks(tasks,title=f"Task(s) for {user['username']}")
            
            if status_code == 200:
                return render_template("tasks.html", title=title, full_list=li, full_list_json=json.dumps(strip_images(li))), 200
        
        return render_template("result.html",title="No Tasks Currently!",msg="The following user currently has no tasks assigned to him. Click okay to add a task for them.",color=RED,image=ERROR,rd="tasks.add_task"),404

    return abort(401)

def order(sort_by, user_id=None):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    valid_sorts = {
        "id": "id ASC",
        "assigned_to": "assigned_to.username ASC",
        "assigned_by": "assigned_by.username ASC",
        "status": "status = 'Pending' DESC, id ASC",
        "start_date": "start_date ASC",
        "end_date": "end_date ASC",
        "priority": "FIELD(priority, 'Urgent', 'Important', 'Least Important') ASC",
    }

    query = """
        SELECT t.*, assigned_to.username AS assigned_to_name, assigned_by.username AS assigned_by_name
        FROM tasks t
        JOIN users assigned_to ON t.user_id = assigned_to.id
        JOIN users assigned_by ON t.assigned_by = assigned_by.id
    """
    params = []

    if user_id is not None:
        query += " WHERE t.user_id = %s"
        params.append(user_id)
    elif user_id is None and not is_admin():
        query += " WHERE t.user_id = %s"
        params.append(current_user.id)

    # else: Admin with no user_id – show all

    if sort_by in valid_sorts:
        query += f" ORDER BY {valid_sorts[sort_by]}"

    cursor.execute(query, params)
    return cursor.fetchall()

def get_tasks(tasks,title):
    user = current_user
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    users = []
    l = []

    # base64_images = []
    # for img in tasks:
    #     if img['image'] is not None:
    #         base64_img = b64encode(img['image']).decode('utf-8')
    #     else:
    #         base64_img = ""
    #     base64_images.append(base64_img)

    if not tasks:
        li = []
        title = "No Task Assigned Currently!"
        status_code = 404
        return (li,title,status_code)
    
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

            for user,task,assigned in zip(users,tasks,assigned_by_list):
                if user['username'] is not None:
                    l.append((f"{user['first_name']} {user['last_name']}",task,assigned))
                else:
                    l.append(("Deleted User",task,assigned))
        else:
            now = datetime.now().date()
            cursor.execute("SELECT * FROM users WHERE id = %s",(current_user.id,))
            user = cursor.fetchone()

            for task,assigned in zip(tasks,assigned_by_list):
                task_start = task['start_date']

                if task['status'] == "Pending" and task_start <= now:
                    l.append((f"{user['first_name']} {user['last_name']}", task, assigned))

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
        priority = request.form['priority']

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
            (user_id,task,image_data,start_date,end_date,currentdt,assigned_by,status,priority)
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
            return render_template("tasks.html", title=title, full_list=li, full_list_json=json.dumps(strip_images(li))), 200
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
        return render_template("tasks.html", title=title, full_list=li, full_list_json=json.dumps(strip_images(li))), 200
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
            return render_template("tasks.html", title=title, full_list=li, full_list_json=json.dumps(strip_images(li))), 200
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
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM tasks WHERE id = %s",(task_id,))
    cursor.execute("SELECT * FROM users WHERE id = %s",(cursor.fetchone()['user_id'],))
    user = cursor.fetchone()
    if is_admin() or user['id'] == current_user.id:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("UPDATE tasks SET status = %s WHERE id = %s",("Complete",task_id))
        mysql.connection.commit()

        cursor.execute("SELECT * FROM tasks")
        tasks = cursor.fetchall()
        li,title,status_code = get_tasks(tasks=tasks,title=f"Task {task_id} marked Complete!")
        
        if status_code == 200:
            return render_template("tasks.html", title=title, full_list=li, full_list_json=json.dumps(strip_images(li))), 200
        else:
            abort(404)
    else:
        abort(401)

def build_comment_tree(comments):
    children_map = defaultdict(list)
    
    for comment in comments:
        parent_id = comment['parent_id']
        if parent_id:
            children_map[parent_id].append(comment)

    def attach_children(comment):
        comment['replies'] = []
        for child in children_map.get(comment['id'],[]):
            attach_children(child)
            comment['replies'].append(child)
    
    root_comments = []
    for comment in comments:
        if comment['parent_id'] is None:
            attach_children(comment)
            root_comments.append(comment)

    return root_comments

@bp.route('/task/<int:task_id>',methods=['GET','POST'])
@login_required
def view_task(task_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM tasks WHERE id=%s",(task_id,))
    task = cursor.fetchone()

    if is_admin() or task['user_id'] == current_user.id:
        cursor.execute("SELECT first_name,last_name FROM users WHERE id=%s",(task['assigned_by'],))
        assigned_by = cursor.fetchone()

        cursor.execute("SELECT first_name,last_name FROM users WHERE id=%s",(task['user_id'],))
        assigned_to = cursor.fetchone()

        if task and task['image']:
            task['image'] = b64encode(task['image']).decode('utf-8')
        else:
            task['image'] = ""
        
        cursor.execute("SELECT * FROM comments WHERE task_id = %s",(task_id,))
        comments = cursor.fetchall()

        c = build_comment_tree(comments)
        print(c)

        def enrich_comment(comment):
            cursor.execute("SELECT first_name, last_name, profile_picture FROM users WHERE id = %s", (comment['user_id'],))
            user = cursor.fetchone()

            if user and user.get('profile_picture'):
                user['profile_picture'] = b64encode(user['profile_picture']).decode('utf-8')
            else:
                user['profile_picture'] = ""

            comment['user'] = user

            # Color
            comment['color'] = random.choice(comment_colors)

            for reply in comment.get('replies', []):
                enrich_comment(reply)

        for comment in c:
            enrich_comment(comment)

        return render_template("view_task.html",title=f"Task {task_id}",task=task,assigned_by=assigned_by,assigned_to=assigned_to,comments=c)
    
    return abort(401)

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
                return render_template("tasks.html", title=title, full_list=li, full_list_json=json.dumps(strip_images(li))), 200
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

# Progress 
@bp.route('/progress')
@login_required
def progress():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users")
    all_users = cursor.fetchall()

    for user in all_users:
        cursor.execute("SELECT status from tasks WHERE user_id = %s",(user['id'],))
        status = cursor.fetchall()
        c = 0
        for s in status:
            if s['status'] == "Complete": c+=1
        if len(status) == 0:
            percent = 0
        else:
            percent = c/len(status)*100
            
        user['percentage'] = str(round(percent,3))
        if percent in range(80,101):
            user['bg'] = "success"
        elif percent in range(50,81):
            user['bg'] = "info"
        elif percent in range(30,51):
            user['bg'] = "warning"
        else:
            user['bg'] = "danger"

    return render_template("progress.html",users=all_users,title="Tasks Progress for All Users")

# Comments
@bp.route('/add_comment/<int:task_id>',methods=['POST'])
@login_required
def add_comment(task_id):
    comment_txt = request.form.get("comment")
    parent_id = request.form.get("parent_id") 

    if comment_txt == "":
        return render_template("result.html",title="No Text Entered",msg="Enter some text for a comment to be displayed",color=RED,image=ERROR,rd="tasks.view_tasks"),206 

    if not parent_id:
        parent_id = None
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        "INSERT INTO comments (task_id, user_id, txt, parent_id) VALUES (%s, %s, %s, %s)",
        (task_id, current_user.id, comment_txt, parent_id)
    )
    mysql.connection.commit()

    return redirect(url_for("tasks.view_task", task_id=task_id))

@bp.route('/delete_comment/<int:comment_id>/<int:task_id>',methods=['POST'])
@login_required
def delete_comment(comment_id,task_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM comments WHERE id = %s",(comment_id,))
    comment = cursor.fetchone()

    if comment['user_id'] == current_user.id or is_admin():
        cursor.execute("DELETE FROM comments WHERE id = %s",(comment_id,))
        mysql.connection.commit()

        return redirect(url_for("tasks.view_task", task_id=task_id))
    else:
        abort(401)