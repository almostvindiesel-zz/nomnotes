import os

from flask import Flask
app = Flask(__name__)

from app import app
from nomnotes import views

