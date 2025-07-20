from flask import Flask
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from flask_session import Session
from dotenv import load_dotenv
import os

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

    from app.routes import auth, tasks, users
    app.register_blueprint(auth.bp,url_prefex='')
    app.register_blueprint(tasks.bp,url_prefex='')
    app.register_blueprint(users.bp,url_prefex='')

    return app
