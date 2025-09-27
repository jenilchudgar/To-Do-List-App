from flask import Blueprint, render_template, request,redirect,url_for,abort,session
from flask_login import login_required, current_user
from flask_socketio import emit, join_room
from app import mysql, bcrypt
from flask_mysqldb import MySQLdb
from flask_mysqldb import MySQL
from flask_socketio import SocketIO
import uuid
from app.constants import *

mysql = MySQL()
socketio = SocketIO()

bp = Blueprint("board", __name__, url_prefix="/board")

ACTIVE = "active"

@bp.route('/check/<int:task_id>',methods=['GET','POST'])
@login_required
def check(task_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM boards WHERE task_id = %s AND state = %s",(task_id,ACTIVE))
    board = cursor.fetchone()
    
    cursor.execute("SELECT * FROM tasks WHERE id = %s",(task_id,))
    task = cursor.fetchone()
    
    if board:
        board_id = board['id']
        return redirect(url_for('board.wave', board_id=board_id))
    else:
        if current_user.role == "admin" or current_user.id == task['user_id']:
            return redirect(url_for('board.new_wave',task_id=task_id))
        else:
            abort(404)

@bp.route('/new_wave/<int:task_id>',methods=['GET','POST'])
@login_required
def new_wave(task_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM tasks WHERE id = %s",(task_id,))
    task = cursor.fetchone()

    cursor.execute("SELECT * FROM boards WHERE task_id = %s AND state = %s",(task_id,ACTIVE))
    board = cursor.fetchone()

    if not board:
        if current_user.role == "admin" or current_user.id == task['user_id']:

            if request.method == "POST":
                radio = request.form.get("radio")
                code = uuid.uuid4().hex[:6]
                formatted_code = '-'.join([code[i:i+3] for i in range(0,6,3)])
                code = formatted_code
                
                if radio == "closed":
                    password = request.form.get("password")
                    if password:
                        hashed_pass = bcrypt.generate_password_hash(password).decode('utf-8')
                    else:
                        abort(400)

                    title = f"Closed Room Code"
                    cursor.execute("INSERT INTO boards (task_id,user_id,invite_type,room_code,password,state) VALUES (%s,%s,%s,%s,%s,%s)",(task_id,current_user.id,radio,code,hashed_pass,ACTIVE))
                    
                else:
                    title = f"Open Room Code"
                    cursor.execute("INSERT INTO boards (task_id,user_id,invite_type,state,room_code) VALUES (%s,%s,%s,%s,%s)",(task_id,current_user.id,radio,ACTIVE,code))

                mysql.connection.commit()
                bd = cursor.lastrowid

                return render_template("result.html",title=title,msg=f"Your Room: {code}",color=YELLOW,image=BRAINWAVE,rd="board.verify_wave",board_id=bd,code=code),200
            
            return render_template("create_new_wave.html",task_id=task_id)
        return abort(404)
    else:
        abort(401)
        
@bp.route('/wave/<int:board_id>',methods=['GET','POST'])
@login_required
def wave(board_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM boards WHERE id = %s",(board_id,))
    board = cursor.fetchone()

    if not board:
        abort(404)

    if board['invite_type'] == "closed":
        verified = session.get(f"verified_board_{board_id}", False)
        if not verified:
            return redirect(url_for("board.verify_wave", board_id=board_id))

    cursor.execute("SELECT * FROM tasks WHERE id = %s",(board['task_id'],))
    task = cursor.fetchone()

    return render_template("wave.html",task=task,board=board)

@bp.route('/verify_wave/<int:board_id>',methods=['GET','POST'])
@login_required
def verify_wave(board_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM boards WHERE id = %s",(board_id,))
    board = cursor.fetchone()

    if board:
        if request.method == "POST":
            session[f"verified_board_{board_id}"] = True
            pwd = request.form.get("password")
            if bcrypt.check_password_hash(board['password'],pwd):
                return redirect(url_for("board.wave",board_id=board_id))
            else:
                return render_template("result.html",title=f"Incorrect Password",msg=f"The password you entered is incorrect. Please try again.",rd="users.home",image=ERROR,color=RED),401
        
        return render_template("verify_wave.html",board_id=board_id,room_code=board['room_code'])
    else:
        return render_template("result.html",title=f"Board {board_id} doesn't Exist",msg=f"The following board doesn't exist. Please try again for a valid board.",rd="users.home",image=ERROR,color=RED),404