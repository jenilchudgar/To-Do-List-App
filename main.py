from flask_login import LoginManager,UserMixin,login_user,login_required,logout_user,current_user
from flask import Flask,request,render_template,abort,jsonify,session
from datetime import datetime,date as dt, timedelta
from flask_mail import Mail, Message
from flask_session import Session
import re,random,os,json,requests
from flask_bcrypt import Bcrypt
from flask_mysqldb import MySQL
from dotenv import load_dotenv
from time import localtime
import MySQLdb.cursors
from base64 import *

# Constants
GREEN = "#67ffa1"
RED = "#fc4747"
OK = "tick.png"
ERROR = "error.png"

# Flask 
app = Flask(__name__)
app.secret_key = 'SECRET_KEY_2025'
app.url_map.strict_slashes = False

# Set Up Env. Variables
load_dotenv() 

# Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
mail = Mail(app)

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)

# Bcrypt Password Protection
bcrypt = Bcrypt(app)

# MySQL Database Declarations
app.config['MYSQL_PORT'] = 3306
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = 'FLASKBASE'
mysql = MySQL(app)

# Initialize Sessions
app.config["SESSION_PERMANENT"] = False     
app.config["SESSION_TYPE"] = "filesystem"  
Session(app)

# Weather API Call Workings
def get_weather(c:str,cn:str):
    print(f"COUNTRY: {cn}")
    latitude, longitude = 40.7128, -74.0060
    url_geo = "https://geocoding-api.open-meteo.com/v1/search"
    param = {
        "name": c,
    }

    try:
        response = requests.get(url_geo, params=param, timeout=5)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
    except Exception as e:
        print("Geo API error:", e)
        latitude, longitude = 40.7128, -74.0060
        results = []
         
    for res in results:
        if c.lower() in res["name"].lower() and res["country"].lower() == cn.lower():
                print("HERE")
                selected_city = res
                latitude = selected_city["latitude"]
                longitude = selected_city["longitude"]
                break
    
    today = dt.today().strftime('%Y-%m-%d')

    # API endpoint
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join([
            "temperature_2m",
            "apparent_temperature",
            "rain",
            "snowfall",
            "uv_index",
            "relative_humidity_2m",
            "wind_speed_10m"
        ]),
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "auto"
    }

    # Make the request
    response = requests.get(url, params=params)
    data = response.json()

    # Extract current weather
    current = data.get("current", {})
    daily = data.get("daily", {})

    weather_data = {}

    weather_data['temp'] = current.get('temperature_2m', None)
    weather_data['feels_like'] = current.get('apparent_temperature', None)
    weather_data['rain'] = current.get('rain', None)
    weather_data['snow'] = current.get('snowfall', None)
    weather_data['uv'] = current.get('uv_index', None)
    weather_data['humidity'] = current.get('relative_humidity_2m', None)
    weather_data['wind_speed'] = current.get('wind_speed_10m', None)

    # Extract only today's max/min
    if "time" in daily and today in daily["time"]:
        index = daily["time"].index(today)
        weather_data['max_temp'] = daily['temperature_2m_max'][index]
        weather_data['min_temp'] = daily['temperature_2m_min'][index]
    else:
        weather_data['max_temp'], weather_data['min_temp'] = None,None
    
    return weather_data

def update_weather_if_needed(user_data):
    last_fetch_str = session.get("weather_last_fetched", "")
    now = datetime.now()

    if last_fetch_str:
        try:
            last_fetch = datetime.fromisoformat(last_fetch_str)
            if now - last_fetch < timedelta(minutes=30):  # only if <30 mins passed
                print("OLD")
                return session.get("weather_data", {})
        except:
            pass

    weather_data = get_weather(user_data['city'], user_data['country'])
    session["weather_data"] = weather_data
    session["weather_last_fetched"] = now.isoformat()
    print("NEW")
    return weather_data

# User Model
class User(UserMixin):
    def __init__(self,id,username,role):
        self.id = id
        self.username = username
        self.role = role
    
    @staticmethod
    def get(user_id):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE id = %s",(user_id,))
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

# Error Handling
@app.errorhandler(401)
def unauthorized_error(error):
    return render_template("result.html",title="Unauthorized Access!",msg="Kindly login or contact your administrator.",color=RED,image=ERROR,rd="home"),401 

@app.errorhandler(404)
def not_found_error(error):
    return render_template("result.html",title="File or Path Not Found!",msg="The thing you asked for is not available. Try again later.",color=RED,image=ERROR,rd="home"),404

# Updation
@app.before_request
def update():
    if current_user.is_authenticated:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Streak
        cursor.execute("SELECT * FROM users WHERE id = %s",(current_user.id,))
        user = cursor.fetchone()
        ls = user['last_seen'].date()
        today = dt.today()

        if ls == today:
            # Already Updated
            pass
        elif ls == today - timedelta(days=1):
            cursor.execute("UPDATE users SET streak = %s WHERE id = %s",(user['streak'] + 1,current_user.id))
        else:
            cursor.execute("UPDATE users SET streak = %s WHERE id = %s",(1,current_user.id))
        
        # Last Seen
        last_seen = datetime.now()
        cursor.execute("UPDATE users SET last_seen = %s WHERE id = %s",(last_seen,current_user.id))

        mysql.connection.commit()

# Login and Registration
@app.route('/login',methods=['POST','GET'])
def login():
    if request.method == "POST" and 'username' in request.form and 'password' in request.form:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        username = request.form['username']
        password = request.form['password']
        msg=""

        cursor.execute("SELECT * FROM users WHERE USERNAME = %s",(username,))
        acc = cursor.fetchone()
        if acc:
            session.clear()

            is_valid = bcrypt.check_password_hash(acc['password'], password)
            if is_valid:
                title = "Login Successful!"
                msg = "You have successfully logged into your website. Enjoy the experience and do your tasks deligently."
                rd = "home"
                img = OK
                color = GREEN
                code = 200
                user = User(id=acc['id'],username=acc['username'],role=acc['role'])

                user_data = {
                    "city": acc['city'],
                    "country": acc['country']
                }
                session["weather_data"] = update_weather_if_needed(user_data)

                login_user(user,remember=('check' in request.form))
            else:
                title = "Login Failed!"
                msg = "The Login Failed as you entered the incorrect password. Kindly retry."
                rd = "login"
                img = ERROR
                color = RED
                code = 400
        else:
            title = "Your Account doesn't exist!"
            msg = "The Login Failed as your account doesn't exist in our database. Kindly register first."
            rd = "login"
            img = ERROR
            color = RED
            code = 400
    
        return render_template("result.html",title=title,msg=msg,rd=rd,image=img,color=color),code
    return render_template("login.html")

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method == "POST":
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # All field entries
        first_name = request.form['first_name']
        last_name = request.form['last_name']

        profile_picture = request.files['profile_picture']
        image_data = profile_picture.read()

        username = request.form['username']
        password = request.form['password']

        email = request.form['email']
        valid = re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email)
        
        if not valid:
            return render_template("result.html",title="Invalid Email",msg="The email you entered was incorrect. Kindly enter a valid email.",color=RED,image=ERROR,rd="home"),401

        city = request.form['city']
        state = request.form['state']
        country = request.form['country']
        zip = request.form['zip']

        cursor.execute("SELECT * FROM users WHERE USERNAME = %s",(username, ))
        acc = cursor.fetchone()

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        if acc:
            title = "Account already Exists!" 
            code = 400
            msg = "Kindly login with that account or create a different account."
            img = ERROR
            color=RED
            
            return render_template("result.html",title=title,msg=msg,image=img,color=color,rd="register"),code
        else:
            session['data'] = {
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
                "password": hashed_password,
                "email": email,
                "city": city,
                "state": state,
                "country": country,
                "zip": zip,
                "role": "user",
                "created_on": str(datetime.now()),
                "profile_picture": image_data

            }

            otp = str(random.randint(100000,999999))
            session['otp'] = otp
            message = Message('OTP',sender="todolist.flaskbase@gmail.com",recipients=[email])
            today = datetime.today()
            formatted_date = today.strftime("%B %d, %Y")
            html = render_template("otp_email.html",name=f"{first_name} {last_name}",otp=otp,date=formatted_date,)
            message.html = html
            mail.send(message)

            return render_template('verify_otp.html', email=email,redirect="verify_otp")
    
    return render_template("register.html",title="Register Now!",btn="Register",path="/register")

@app.route('/logout')
@login_required
def logout():
    logout_user() 
    return render_template("result.html",title="Logout Successful!",msg="We're sorry to see you go, do return later to complete your tasks!",color=GREEN,image=OK,rd="home"),200

@app.route('/verify_otp/',methods=['GET','POST'])
def verify_otp():
    otp = ""
    for i in range(6):
        otp = otp + request.form[f'input{i}']

    if session['otp'] == otp:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        created_on = datetime.now()
        data = session['data']
        pic = data['profile_picture']
        last_seen = datetime.now()
        streak = 1
        
        cursor.execute("INSERT INTO users (first_name,last_name,username,password,email,city,state,country,zip,role,created_on,profile_picture,last_seen,streak) VALUES (%s, %s, %s,%s,%s, %s, %s,%s,%s, %s, %s, %s, %s, %s)",
                       (
                           data['first_name'],
                            data['last_name'],
                            data['username'],
                            data['password'],
                            data['email'],
                            data['city'],
                            data['state'],
                            data['country'],
                            data['zip'],
                            data['role'],
                            created_on,
                            pic,
                            last_seen,
                            streak
                        )
                    )

        mysql.connection.commit()

        title = "You have successfully registered!"
        msg = "Thank you for registering on our websites. Enjoy the website experience!"
        img = OK
        color=GREEN

        code = 200
        session.clear()
        
    else:
        title = "Incorrect OTP!"
        msg = "The OTP you entered was incorrect. Kindly retry."
        img = ERROR
        color=RED
        
        code = 422

    return render_template("result.html",title=title,msg=msg,image=img,color=color,rd="login"),code

# CRUD Operations for Tasks
@app.route('/view_user_tasks/<int:user_id>',methods=['GET'])
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

@app.route('/tasks',methods=['GET'])
@login_required
def view_task():
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

def order(sort_by):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    valid_sorts = {
        "id":"id ASC",
        "assigned_to":"assigned_to.username ASC",
        "assigned_by":"assigned_by.username ASC",
        "status":"status = 'Pending' DESC, id ASC",
        "start_date":"start_date ASC",
        "end_date":"end_date ASC",
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

    query += f" ORDER BY {valid_sorts.get(sort_by)}"
    
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

@app.route('/add_task/',methods=['GET','POST'])
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

@app.route('/mark_complete/<int:task_id>')
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
@app.route('/reassign',methods=['GET','POST'])
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

@app.route('/reassign_task/<int:task_id>')
@login_required
def reassign_task(task_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    return render_template("reassign.html",title="Select the user who you want to reassign the task to",users=users,task_id=task_id)

# Index Page (Home)
@app.route('/',methods=['GET'])
def home():
    is_user = current_user.is_authenticated
    tasks = []
    col_names = []
    base64_img = ""
    id = 0
    user = current_user
    users = []
    new_users = []
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
            list(new_users),k=min(3,len(new_users))
        )
    )

@app.route('/search',methods=['GET','POST'])
@login_required
def search():
    if request.method == "POST" and "search_box" in request.form:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        q = request.form['search_box']
        by = request.form['by']
        
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
        except:
            abort(401) 
        tasks = cursor.fetchall()

        if is_admin():
            title = f'Search Results for {by} with "{q}" from all users'
        else:
            title = f'Search Results for {by} with 25"{q}"'

        li,title,status_code = get_tasks(tasks,title)
        
        if status_code == 200:
            return render_template("tasks.html",title=title,full_list=li),status_code
        else:
            abort(404)

    return render_template("index.html"),400

# CRUD Operations for Users
@app.route('/users',methods=['GET'])
@login_required
def view_users():
    if is_admin():
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        return render_template("users.html",admin=is_admin(),users=users),200
    else:
        return render_template("result.html",title="Unauthorized Access!",msg="The following site can only be accessed by an admin. Contact your administrator for more information.",color=RED,image=ERROR,rd="home"),401

@app.route('/update_user/<int:user_id>',methods=['GET',"POST"])
@login_required
def update_user(user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s",(user_id,))
    user = cursor.fetchone()

    if not user or not(user['id'] == current_user.id):
        return abort(404)
    
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
        return render_template("result.html", title="Profile Updated!", msg="Your profile has been successfully updated.", color=GREEN, image=OK, rd="home")


    return render_template("register.html",user=user,title="Update your Profile",path=f"/update_user/{user_id}",btn="Update")

@app.route('/delete_user/<int:user_id>',methods=['GET','POST'])
@login_required
def delete_user(user_id):
    if is_admin():
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("DELETE FROM users WHERE id =  %s",(user_id,))
        cursor.execute("DELETE FROM tasks WHERE user_id = %s",(user_id,))

        mysql.connection.commit()
        
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()

        return render_template("users.html",users=users)

    return render_template("result.html",title="Unauthorized Access!",msg="The following site can only be accessed by an admin. Contact your administrator for more information.",color=RED,image=ERROR,rd="home"),401

@app.route('/change_role/<int:user_id>',methods=['GET','POST'])
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
    
    return render_template("result.html",title="Unauthorized Access!",msg="The following site can only be accessed by an admin. Contact your administrator for more information.",color=RED,image=ERROR,rd="home"),401

@app.route('/profile/<int:user_id>')
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

@app.route('/change_password/<int:user_id>',methods=['GET','POST'])
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
        return render_template('verify_otp.html',redirect="password")
        
    else:
        return render_template("change_password.html")

@app.route('/password', methods=['GET', 'POST'])
@login_required
def password():
    user_id = current_user.id
    password1 = session['password1']
    password2 = session['password2']
    old_pass = session['old_pass']
    if password1 == old_pass or password2 == old_pass:
        return render_template("result.html",title="Same Passwords!",msg="The new and old passwords were same. Kindly retry.",color=RED,image=ERROR,rd="home"),404
    
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
                return render_template("result.html",title="Password Changed Successfully!",msg="Your password has now been updated. Kindly login again to continue for work.",color=GREEN,image=OK,rd="login"),200
            
            else:
                return render_template("result.html",title="The password didn't match.",msg="The new passwords you entered didn't match kindly retry.",color=RED,image=ERROR,rd="home"),404

if __name__ == '__main__':
    app.run(debug=True)