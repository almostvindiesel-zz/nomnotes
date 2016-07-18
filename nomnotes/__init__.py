from flask import Flask
app = Flask(__name__)

app.config.from_envvar('NOMNOTES_SETTINGS', silent=True)


import nomnotes.views


