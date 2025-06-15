from flask import Blueprint, request, render_template, session
from flask_login import login_user, login_required, logout_user
from app.models import User
from app import mysql, bcrypt, login_manager, mail
from flask_mail import Message
import re,random
from flask_mysqldb import MySQLdb
from datetime import datetime
from app.utils import *
from app.constants import *

bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@bp.route('/login', methods=['GET', 'POST'])
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
                rd = "users.home"
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
                rd = "auth.login"
                img = ERROR
                color = RED
                code = 400
        else:
            title = "Your Account doesn't exist!"
            msg = "The Login Failed as your account doesn't exist in our database. Kindly register first."
            rd = "auth.login"
            img = ERROR
            color = RED
            code = 400
    
        return render_template("result.html",title=title,msg=msg,rd=rd,image=img,color=color),code
    return render_template("login.html")

@bp.route('/register', methods=['GET', 'POST'])
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
            return render_template("result.html",title="Invalid Email",msg="The email you entered was incorrect. Kindly enter a valid email.",color=RED,image=ERROR,rd="auth.home"),401

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
            
            return render_template("result.html",title=title,msg=msg,image=img,color=color,rd="auth.register"),code
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

            return render_template('verify_otp.html', email=email,redirect="auth.verify_otp")
    
    return render_template("register.html",title="Register Now!",btn="Register",path="/register")

@bp.route('/logout')
@login_required
def logout():
    logout_user() 
    return render_template("result.html",title="Logout Successful!",msg="We're sorry to see you go, do return later to complete your tasks!",color=GREEN,image=OK,rd="users.home"),200

@bp.route('/verify_otp', methods=['POST'])
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

    return render_template("result.html",title=title,msg=msg,image=img,color=color,rd="auth.login"),code
