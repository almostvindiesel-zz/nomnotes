import os


#app.config.from_envvar('NOMNOTES_SETTINGS', silent=True)


if os.environ["NOMNOMTES_ENVIRONMENT"] == 'local':
	from flask import Flask
	app = Flask(__name__)

	app.config['HOSTNAME'] = 'http://localhost:5000'
	app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://mars:iloveb8con@localhost/nomnotes'
	app.config['SQLALCHEMY_POOL_RECYCLE'] = 299
	app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = 'False'

	app.config['DEBUG'] = True
	app.config['SECRET_KEY'] = '2?12z8+O?l9+:D1ibWwe".FGn9QIRA'

	app.config['MAIL_USERNAME'] = 'jmarsland@gmail.com'
	app.config['MAIL_PASSWORD'] = 'z1qGW4ZGg'
	app.config['MAIL_DEFAULT_SENDER'] = '"Nom Notes" <jmarsland@gmail.com>'
	app.config['MAIL_SERVER'] = 'smtp.gmail.com'
	app.config['MAIL_PORT'] = 465
	app.config['MAIL_USE_SSL'] = True
	app.config['MAIL_USE_TLS'] = False

	import nomnotes.views

	#SQLALCHEMY_DATABASE_URI_POSTGRE = 'postgresql://mars:iloveb8con@localhost/nomnotes'
	#SQLALCHEMY_DATABASE_URI_SQLITE = 'sqlite:////Users/mars/code/nomnotes/nomnotes.db'


#elif(os.environ["NOMNOMTES_ENVIRONMENT"] == 'pythonanywhere'):
	# Do Nothing


