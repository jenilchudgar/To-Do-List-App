from flask import request,render_template,abort,session,Blueprint,send_file,redirect,url_for
from flask_login import login_required,current_user
from datetime import datetime
from flask_mail import Message
import random,json
from app.constants import *
from app.utils import *
from time import localtime
import MySQLdb.cursors
from app import mysql,mail
from base64 import *
import bcrypt
from app.routes.tasks import get_tasks,strip_images
import io


bp = Blueprint('users', __name__)

# Index Page (Home)
@bp.route('/',methods=['GET'])
def home():
    is_user = current_user.is_authenticated
    tasks = []
    col_names = []
    base64_img = ""
    id = 0
    user = current_user
    users = []
    new_users = []
    weather_class = ""
    state = ""
    if is_user:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM INFORMATION_SCHEMA.COLUMNS where TABLE_NAME='tasks'")

        tasks = cursor.fetchall()
        col_names = []
        for task in tasks:
            col = task['COLUMN_NAME']
            if col in ["currentdt","image",]:
                continue
        
            col_names.append(str(col))
        
        cursor.execute("SELECT * FROM users WHERE id = %s",(current_user.id,))
        user = cursor.fetchone()

        user_data = {
            "city": user['city'],
            "country": user['country']
        }

        weather_data = update_weather_if_needed(user_data)
        weather_class = ""

        if 6 <= localtime().tm_hour < 18:
            # Day
            if weather_data['snow']:
                weather_data['icon'] = "snow.png"
                weather_class = "snowy"
            elif weather_data['rain']:
                weather_data['icon'] = "dark-blue"
                weather_class = "rain"
            else:
                weather_data['icon'] = "sun.png"
                weather_class = "light-blue"
        else:
            # Night
            weather_data['icon'] = "night.png"
            weather_class = "blackish"

        base64_img = b64encode(user['profile_picture']).decode('utf-8')

        id = current_user.id

        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        time = datetime.now()

        new_users = []

        for u in users:
            if u['id'] == user['id']:
                continue
            if u['profile_picture']:
                u['profile_picture'] = b64encode(u['profile_picture']).decode('utf-8')
                diff = time - u['last_seen']
                seconds = diff.total_seconds()

                if seconds <= 10:
                    u['last_seen'] = "Just now"
                    state = "Online"
                elif seconds < 60:
                    u['last_seen'] = f"A few seconds ago"
                    state = "Offline"
                elif seconds < 3600:
                    minutes = int(seconds / 60)
                    u['last_seen'] = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
                    state = "Offline"
                elif seconds < 86400:
                    hours = int(seconds / 3600)
                    u['last_seen'] = f"{hours} hour{'s' if hours != 1 else ''} ago"
                    state = "Offline"
                elif seconds < 604800:  
                    days = int(seconds // 86400)
                    u['last_seen'] = f"{days} day{'s' if days != 1 else ''} ago"
                    state = "Offline"
                else:
                    u['last_seen'] = "A long time ago"
                    state = "Offline"
                
                new_users.append((u,state))
    
    else:
        weather_data = None

    return render_template("index.html",is_user=is_user,admin=is_admin(),user=user,col_names=col_names,img=base64_img,id=id,weather_data=weather_data,weather_class=weather_class,today=datetime.today().strftime(r"%B %d, %Y"),last_seen_users=random.sample(
            list(new_users),k=min(2,len(new_users))
        )
    )

@bp.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    if request.method == "POST":
        q = request.form.get("search_box", "").strip()
        by = request.form.get("by", "").strip()
        sort_by = request.form.get("sort_by")
        full_list_json = request.form.get("full_list_json")

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Handle case where full_list_json is passed for sorting only (no DB fetch again)
        if full_list_json and sort_by:
            try:
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
                title = f'Sorted Search Results by {sort_by.replace("_", " ").capitalize()}'

                return render_template("tasks.html", title=title, full_list=li, full_list_json=json.dumps(strip_images(li))), 200

            except Exception as e:
                print("Sorting Error:", e)
                return render_template("result.html", title="Sorting Failed", msg="Sorting of tasks failed.", color="danger", image=ERROR, rd="tasks.view_tasks"), 400

        # Normal search query
        query = "SELECT * FROM tasks WHERE "
        params = []

        if is_admin():
            if by in ["start_date", "end_date"]:
                query += f"DATE({by}) = %s"
                params.append(q)
            else:
                query += f"{by} LIKE %s"
                params.append(f"%{q}%")
        else:
            if by in ["start_date", "end_date"]:
                query += f"DATE({by}) = %s AND user_id = %s"
                params.extend([q, current_user.id])
            else:
                query += f"{by} LIKE %s AND user_id = %s"
                params.extend([f"%{q}%", current_user.id])

        try:
            cursor.execute(query, params)
        except Exception as e:
            print("DB Search Error:", e)
            return render_template("result.html", title="Invalid Search", msg="Your query is invalid.", color=RED, image=ERROR, rd="tasks.view_tasks"), 400

        tasks = cursor.fetchall()
        title = f'Search Results for "{q}" in {by}'
        if is_admin():
            title += " (All Users)"
        else:
            title += " (Your Tasks Only)"

        li, title, status_code = get_tasks(tasks, title)

        if status_code == 200:
            return render_template("tasks.html", title=title, full_list=li, full_list_json=json.dumps(strip_images(li))), 200
        else:
            return render_template("result.html", title="No Results Found", msg="No matching tasks found.", color="warning", image=ERROR, rd="tasks.view_tasks"), 404

    return render_template("index.html", title="Search Tasks"), 400

# CRUD Operations for Users
@bp.route('/users',methods=['GET'])
@login_required
def view_users():
    if is_admin():
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        return render_template("users.html",admin=is_admin(),users=users),200
    else:
        return render_template("result.html",title="Unauthorized Access!",msg="The following site can only be accessed by an admin. Contact your administrator for more information.",color=RED,image=ERROR,rd="users.home"),401

@bp.route('/update_user/<int:user_id>',methods=['GET',"POST"])
@login_required
def update_user(user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s",(user_id,))
    user = cursor.fetchone()

    if not user or not(user['id'] == current_user.id):
        return render_template("result.html",title="Your account doesn't exist.",msg="Your account has not been found on the website. Please register to update your profile",rd="users.register",image=ERROR,color=RED),404
    
    if request.method == "POST":
        first_name = request.form['first_name']
        last_name = request.form['last_name']

        username = request.form['username']

        email = request.form['email']

        city = request.form['city']
        state = request.form['state']
        country = request.form['country']
        zip = request.form['zip']

        updated_on = datetime.now()
        profile_picture = request.files['profile_picture']

        if profile_picture:
            image_data = profile_picture.read()

            cursor.execute("UPDATE users SET first_name = %s, last_name = %s, username = %s, email = %s, city = %s, state = %s, country = %s, zip = %s, updated_on = %s, profile_picture = %s WHERE id = %s",(first_name,last_name,username,email,city,state,country,zip,updated_on,image_data,current_user.id))
        else:
            cursor.execute("UPDATE users SET first_name = %s, last_name = %s, username = %s, email = %s, city = %s, state = %s, country = %s, zip = %s, updated_on = %s WHERE id = %s",(first_name,last_name,username,email,city,state,country,zip,updated_on,current_user.id))

        mysql.connection.commit()
        return render_template("result.html", title="Profile Updated!", msg="Your profile has been successfully updated.", color=GREEN, image=OK, rd="users.home")


    return render_template("register.html",user=user,title="Update your Profile",path=f"/update_user/{user_id}",btn="Update")

@bp.route('/delete_user/<int:user_id>',methods=['GET','POST'])
@login_required
def delete_user(user_id):
    if is_admin():
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("DELETE FROM users WHERE id =  %s",(user_id,))
        cursor.execute("DELETE FROM tasks WHERE user_id = %s",(user_id,))

        mysql.connection.commit()
        
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()

        return redirect(url_for('users.home'))

    return render_template("result.html",title="Unauthorized Access!",msg="The following site can only be accessed by an admin. Contact your administrator for more information.",color=RED,image=ERROR,rd="users.home"),401

@bp.route('/change_role/<int:user_id>',methods=['GET','POST'])
@login_required
def change_role(user_id):
    if is_admin():
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
        cursor.execute("SELECT * FROM users WHERE id = %s",(user_id,))
        user = cursor.fetchone()

        if user['role'] == "admin":
            role = "user"
        else:
            role = "admin"

        cursor.execute("UPDATE users SET role = %s WHERE id = %s",(role,user_id,))
        mysql.connection.commit()
        
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()

        return render_template("users.html",users=users,admin=is_admin())
    
    return render_template("result.html",title="Unauthorized Access!",msg="The following site can only be accessed by an admin. Contact your administrator for more information.",color=RED,image=ERROR,rd="users.home"),401

@bp.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s",(user_id,))
    user = cursor.fetchone()
    user['profile_picture'] = b64encode(user['profile_picture']).decode('utf-8')
    with open("static/json/country_codes.json","r") as f:
        data = json.load(f)

    code = "in"
    for key,value in data.items():
        if user['country'] in value:
            code = key
            break

    return render_template("profile.html",user=user,code=code)

@bp.route('/change_password/<int:user_id>',methods=['GET','POST'])
@login_required
def change_password(user_id):
    if (current_user.id == user_id) and request.method == "POST":
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE id = %s",(user_id,))
        user = cursor.fetchone()

        session['password1'] = request.form['password1']
        session['password2'] = request.form['password2']
        session['old_pass'] = request.form['old_pass']
        
        otp = str(random.randint(100000,999999))
        session['otp'] = otp
        message = Message('OTP',sender="todolist.flaskbase@gmail.com",recipients=[user['email']])
        today = datetime.today()
        formatted_date = today.strftime("%B %d, %Y")
        html = render_template("otp_email.html",name=f"{user['first_name']} {user['last_name']}",otp=otp,date=formatted_date,)
        message.html = html
        mail.send(message)
        return render_template('verify_otp.html',redirect="auth.password")
        
    else:
        return render_template("change_password.html")

@bp.route('/password', methods=['GET', 'POST'])
@login_required
def password():
    user_id = current_user.id
    password1 = session['password1']
    password2 = session['password2']
    old_pass = session['old_pass']
    if password1 == old_pass or password2 == old_pass:
        return render_template("result.html",title="Same Passwords!",msg="The new and old passwords were same. Kindly retry.",color=RED,image=ERROR,rd="users.home"),404
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s",(user_id,))
    user = cursor.fetchone()
    
    otp = ""
    if bcrypt.check_password_hash(user['password'],old_pass):
        for i in range(6):
            otp = otp + request.form[f'input{i}']

        if session['otp'] == otp:
            if password1 == password2:
                hashed_pass = bcrypt.generate_password_hash(password1).decode('utf-8')
                cursor.execute("UPDATE users SET password = %s WHERE id = %s",(hashed_pass,user_id))
                mysql.connection.commit()
                return render_template("result.html",title="Password Changed Successfully!",msg="Your password has now been updated. Kindly login again to continue for work.",color=GREEN,image=OK,rd="users.login"),200
            
            else:
                return render_template("result.html",title="The password didn't match.",msg="The new passwords you entered didn't match kindly retry.",color=RED,image=ERROR,rd="users.home"),404

@bp.route('/downloads',methods=['GET','POST'])
@login_required
def downloads():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == "POST":
        option = int(request.form.get("option"))
        if option in (2,4) and current_user.role != "admin":
            abort(401)

        match option:
            case 1:
                # Download JSON - Tasks for a User
                cursor.execute("SELECT * FROM tasks WHERE user_id = %s",(current_user.id,))
                tasks = cursor.fetchall()
                for task in tasks:
                    task.pop('image', None)  

                json_data = json.dumps(tasks, indent=4, default=str)  
                buffer = io.BytesIO()
                buffer.write(json_data.encode('utf-8'))
                buffer.seek(0)

                return send_file(
                    buffer,
                    mimetype='application/json',
                    as_attachment=True,
                    download_name=f'tasks-user-{current_user.id}.json'
                )

            case 2:
                cursor.execute("SELECT * FROM tasks")
                tasks = cursor.fetchall()
                for task in tasks:
                    task.pop('image', None)  

                json_data = json.dumps(tasks, indent=4, default=str)  
                buffer = io.BytesIO()
                buffer.write(json_data.encode('utf-8'))
                buffer.seek(0)

                return send_file(
                    buffer,
                    mimetype='application/json',
                    as_attachment=True,
                    download_name='all_tasks.json'
                )
    else:
        cursor.execute("SELECT * FROM users WHERE id = %s",(current_user.id,))
        return render_template("downloads.html",user=cursor.fetchone()['username'])