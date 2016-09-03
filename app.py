import os
os.environ['NOMNOMTES_ENVIRONMENT'] = 'heroku'

from nomnotes import app

from flask import Flask
app = Flask(__name__)

import nomnotes
from nomnotes import views


"""
from app import app
from nomnotes import nomnotes
import views
"""