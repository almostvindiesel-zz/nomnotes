import os
from flask import Flask
app = Flask(__name__)

if os.environ["NOMNOMTES_ENVIRONMENT"] == 'pythonanywhere':
	app.config['HOSTNAME'] = 'http://almostvindiesel.pythonanywhere.com/'
	SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://{username}:{password}@{hostname}/{databasename}".format(
	    username="almostvindiesel",
	    password="iloveb8con",
	    hostname="almostvindiesel.mysql.pythonanywhere-services.com",
	    databasename="almostvindiesel$nomnotes?charset=utf8",
	    )
	app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
	app.config['SQLALCHEMY_POOL_RECYCLE'] = 299
	app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = 'False'
	app.config['SQLALCHEMY_POOL_RECYCLE'] = 7200

	app.config['DEBUG'] = True
	app.config['SECRET_KEY'] = '2?12z8+O?l9+:D1ibWwe".FGn9QIRA'

	app.config['MAIL_USERNAME'] = 'jmarsland@gmail.com'
	app.config['MAIL_PASSWORD'] = 'z1qGW4ZGg'
	app.config['MAIL_DEFAULT_SENDER'] = '"Nom Notes" <jmarsland@gmail.com>'
	app.config['MAIL_SERVER'] = 'smtp.gmail.com'
	app.config['MAIL_PORT'] = 465
	app.config['MAIL_USE_SSL'] = True
	app.config['MAIL_USE_TLS'] = False

	from app import app
	import views

