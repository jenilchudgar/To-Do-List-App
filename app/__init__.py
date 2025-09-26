from flask import Flask, render_template
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from flask_session import Session
from dotenv import load_dotenv
import os
from app.constants import RED, ERROR

mysql = MySQL()
bcrypt = Bcrypt()
login_manager = LoginManager()
mail = Mail()
sess = Session()

def create_app():
    app = Flask(__name__)
    app = Flask(__name__, template_folder="../templates",static_folder='../static')
    app.url_map.strict_slashes = False

    app.config.from_mapping(
        SECRET_KEY='SECRET_KEY_2025',
        MYSQL_HOST='localhost',
        MYSQL_USER='root',
        MYSQL_PASSWORD=os.getenv('MYSQL_PASSWORD'),
        MYSQL_DB='FLASKBASE',
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
        MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
        SESSION_PERMANENT=False,
        SESSION_TYPE="filesystem"
    )

    load_dotenv()

    mysql.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    sess.init_app(app)

    from app.routes import auth, tasks, users, board
    app.register_blueprint(auth.bp,url_prefex='')
    app.register_blueprint(tasks.bp,url_prefex='')
    app.register_blueprint(users.bp,url_prefex='')
    app.register_blueprint(board.bp,url_prefex='')

    return app

app = Flask(__name__)

@app.errorhandler(404)
def not_found_error(error):
    return render_template(
        "result.html",
        title="Not Found",
        msg="The page or resource you are looking for does not exist.",
        color=RED,
        image=ERROR,
        rd="tasks.add_task" 
    ), 404

@app.errorhandler(401)
def unauthorized_error(error):
    return render_template(
        "result.html",
        title="Unauthorized Error",
        msg="You are not authorized to access this resource.",
        color=RED,
        image=ERROR,
        rd="tasks.add_task"
    ), 401

@app.errorhandler(500)
def internal_error(error):
    return render_template(
        "result.html",
        title="Internal Server Error",
        msg="Something went wrong on our side. Please try again later.",
        color=RED,
        image=ERROR,
        rd="tasks.add_task"
    ), 500

