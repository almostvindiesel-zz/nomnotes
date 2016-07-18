import sqlite3
from flask import Flask, g
from nomnotes import app
from flask_sqlalchemy import SQLAlchemy
from flask_user import login_required, UserManager, UserMixin, SQLAlchemyAdapter
from sqlalchemy.sql import func
from sqlalchemy import UniqueConstraint, distinct, func
from sqlalchemy.exc import IntegrityError


db = SQLAlchemy(app)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    # User authentication information
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False, server_default='')
    reset_password_token = db.Column(db.String(100), nullable=False, server_default='')

    # User email information
    email = db.Column(db.String(255), nullable=False, unique=True)
    confirmed_at = db.Column(db.DateTime())

    # User information
    active = db.Column('is_active', db.Boolean(), nullable=False, server_default='0')
    first_name = db.Column(db.String(100), nullable=False, server_default='')
    last_name = db.Column(db.String(100), nullable=False, server_default='')




#unique the note and page_url
class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    location_id  = db.Column(db.Integer, db.ForeignKey('location.id'))
    note  = db.Column(db.Text)
    page_url  = db.Column(db.Text)
    added_dt  = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_dt  = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    UniqueConstraint('note', 'location_id', name='note_location_constraint')


    def __init__(self, user_id, location_id, note, page_url):
        self.user_id = user_id
        self.location_id = location_id
        self.note = note
        self.page_url = page_url    

    def __repr__(self):
        return '<User %r>' % self.note

class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer)         #!!! Need to add FK relationship at some point
    name  = db.Column(db.String(255))
    source  = db.Column(db.String(50))
    latitude  = db.Column(db.Float)
    longitude  = db.Column(db.Float)
    city  = db.Column(db.String(50))
    country  = db.Column(db.String(50))
    page_url  = db.Column(db.Text)
    page_title  = db.Column(db.String(255))
    rank  = db.Column(db.String(50))
    rating  = db.Column(db.String(20))
    reviews  = db.Column(db.Integer)
    added_dt  = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_dt  = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    notes = db.relationship('Note', backref='location', lazy='dynamic')
    categories = db.relationship('LocationCategory', backref='location', lazy='dynamic')

    #!!! not sure if this is working with sqlite...
    UniqueConstraint('name', 'source', name='name_source_constraint')

    def __init__(self, parent_id, name, source, latitude, longitude, city, page_url, page_title, rank, rating, reviews):
        self.parent_id = parent_id
        self.name = name
        self.source = source
        self.latitude = latitude
        self.longitude = longitude
        self.city = city
        self.page_url = page_url
        self.page_title = page_title
        self.rank = rank
        self.rating = rating
        self.reviews = reviews

    def __repr__(self):
        return '<User %r>' % self.name

class LocationCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location_id  = db.Column(db.Integer, db.ForeignKey('location.id'))
    category = db.Column(db.String(255))

    def __init__(self, location_id, category):
        self.location_id = location_id
        self.category = category

    def __repr__(self):
        return '<User %r>' % self.category

class LocationParent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<User %r>' % self.name


class SavedUrl(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    url  = db.Column(db.Text, unique=True)
    title  = db.Column(db.String(255))
    city  = db.Column(db.String(50))
    country  = db.Column(db.String(255))

    def __init__(self, user_id, url, title, city, country):
        self.user_id = user_id
        self.url = url
        self.title = title
        self.city = city
        self.country = country

    def __repr__(self):
        return '<User %r>' % self.url

############################################################


def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv


def init_db():  
    """Initializes the database."""
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())

@app.cli.command('initdb')
def initdb_command():
    """ s the database tables."""
    init_db()
    print('Initialized the database.')

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db



