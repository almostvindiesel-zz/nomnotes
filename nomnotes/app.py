import os
os.environ['NOMNOMTES_ENVIRONMENT'] = 'heroku'


from flask import Flask
app = Flask(__name__)

from app import app
import views

