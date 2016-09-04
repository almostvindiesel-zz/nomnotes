import os
import sqlite3
import requests
import urllib
from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from flask_user import login_required, UserManager, UserMixin, SQLAlchemyAdapter
from sqlalchemy.sql import func
from sqlalchemy import UniqueConstraint, distinct, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import relationship

#from flaskext.mysql import MySQL
#import MySQLdb

#print "os environment: ", os.environ["NOMNOMTES_ENVIRONMENT"]

if(os.environ["NOMNOMTES_ENVIRONMENT"] == 'local'):
    from nomnotes import app
elif(os.environ["NOMNOMTES_ENVIRONMENT"] == 'pythonanywhere'):
    from app import app
elif(os.environ["NOMNOMTES_ENVIRONMENT"] == 'heroku'):
    from app import app

db = SQLAlchemy(app)


#!!! combine the methods that parse the venue data from the api
class FoursquareVenue():

    def get(self, foursquare_id, latitude, longitude):

        self.foursquare_id = foursquare_id
        self.latitude = latitude
        self.longitude = longitude
        
        self.name = None
        self.foursquare_url = None
        self.category = None

        self.rating = None
        self.reviews = None

        self.city = None
        self.state = None
        self.country = None
        self.latitude = None
        self.longitude = None

        try: 
            url = 'https://api.foursquare.com/v2/venues/%s/?client_id=%s&client_secret=%s&v=%s&locale=en' % \
                  (self.foursquare_id, app.config['FOURSQUARE_API_CLIENT_ID'], \
                   app.config['FOURSQUARE_API_CLIENT_SECRET'], app.config['FOURSQUARE_API_VERSION'])

            print "--- Foursquare Venue API Url: \r\n", url
            r = requests.get(url)
            venue_json = r.json()
            
            self.foursquare_id = venue_json['response']['venue']['id']
            self.foursquare_url = 'https://foursquare.com/v/' + self.foursquare_id

            self.rating = venue_json['response']['venue']['rating']
            self.reviews = venue_json['response']['venue']['ratingSignals']

        except Exception as e:
            print "Could not augment data from foursquare api: ", e.message, e.args

#alter table location modify longitude Float(10,6)
class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ltype = db.Column(db.String(50))
    latitude  = db.Column(db.Float(12))
    longitude  = db.Column(db.Float(12))
    address1  = db.Column(db.String(50))
    address2  = db.Column(db.String(50))
    city  = db.Column(db.String(50))
    state = db.Column(db.String(50))
    country  = db.Column(db.String(50))
    added_dt  = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_dt  = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    __table_args__ = {'mysql_charset': 'utf8'}

    venue = relationship("Venue", back_populates="location")

    def __init__(self, ltype, city, latitude, longitude):
        self.ltype = ltype
        self.city = city
        self.latitude = latitude
        self.longitude = longitude
        self.address1 = None
        self.address2 = None
        self.state = None
        self.country = None

    def __repr__(self):
        return '<Location %r>' % self.id

    UniqueConstraint('latitude', 'longitude', name='lat_long_constraint')

    def insert(self):
        try:
            db.session.add(self)
            db.session.commit()
            print "--- inserted location:", self.id, self.city, self.latitude, self.longitude
        except Exception as e:
            print "Could not insert location:", self.id, e.message, e.args

    def set_city_state_country_with_lat_lng_from_google_location_api(self):

        try: 
            gurl = 'http://maps.googleapis.com/maps/api/geocode/json?latlng=%s,%s&sensor=false' % (self.latitude, self.longitude)
            print "--- Searching for Location attributes from Google Loc API on lat (%s) long (%s): \r\n %s " % (self.latitude, self.longitude, gurl)

            r = requests.get(gurl)
            g_json = r.json()
            for datums in g_json['results'][0]['address_components']:
                if datums['types'][0] == 'locality':
                    self.city = datums['long_name']
                    print "--- From Google Lat Long API, City:  ", datums['long_name']
                if datums['types'][0] == 'administrative_area_level_1':
                    self.state = datums['long_name']
                    print "--- From Google Lat Long API, State: ", datums['long_name']
                if datums['types'][0] == 'country':
                    self.country = datums['long_name']
                    print "--- From Google Lat Long API, Country: ", datums['long_name']
        
        except Exception as e:
            print "Could not get data from google api api: ", e.message, e.args


    def set_lat_lng_state_from_city_country(self):

        try: 
            gurl = 'https://maps.googleapis.com/maps/api/geocode/json?address=%s&components=country:%s' % (self.city, self.country)
            print "--- Searching for Location attributes from Google Loc API on city (%s) country (%s): \r\n %s " % (self.city, self.country, gurl)

            r = requests.get(gurl)
            g_json = r.json()
            for datums in g_json['results'][0]['address_components']:
            #    if datums['types'][0] == 'locality':
            #        self.city = datums['long_name']
            #        print "--- From Google Lat Long API, City:  ", datums['long_name']
                if datums['types'][0] == 'administrative_area_level_1':
                    self.state = datums['long_name']
                    print "--- From Google Lat Long API, State: ", datums['long_name']
            #    if datums['types'][0] == 'country':
            #        self.country = datums['long_name']
            #        print "--- From Google Lat Long API, State: ", datums['long_name']
            if 'lat' in g_json['results'][0]['geometry']['location']:
                self.latitude = g_json['results'][0]['geometry']['location']['lat']
            if 'lng' in g_json['results'][0]['geometry']['location']:
                self.longitude = g_json['results'][0]['geometry']['location']['lng']
        
        except Exception as e:
            print "Could not get data from google api : ", e.message, e.args
            

class FoursquareVenues():

    def __init__(self, name, city, latitude, longitude):
        self.venues = []  
        self.search_name = name
        self.search_city = city
        self.search_latitude = latitude
        self.search_longitude = longitude

    def search(self):

        #This method uses either city or lat/long to get data from the foursquare api
        #First it tries to find this info via city. If unsuccessful, it then uses lat/long

        #Find venue on foursquare via city:
        url = 'https://api.foursquare.com/v2/venues/search?client_id=%s&client_secret=%s&v=%s&near=%s&query=%s&locale=en' % \
        (app.config['FOURSQUARE_API_CLIENT_ID'], app.config['FOURSQUARE_API_CLIENT_SECRET'], \
         app.config['FOURSQUARE_API_VERSION'], self.search_city, self.search_name )

        print "--- Foursquare Venue Search API Url via city: \r", url

        r = requests.get(url)
        venues_json = r.json()

        #print '-' * 20
        #print venues_json['response']
        #print '-' * 20

        #If no venues are returned, find venue on foursquare via lat long:
        if not venues_json or not len(venues_json['response']):
            url = 'https://api.foursquare.com/v2/venues/search?client_id=%s&client_secret=%s&v=%s&ll=%s,%s&query=%s&locale=en' % \
            (app.config['FOURSQUARE_API_CLIENT_ID'], app.config['FOURSQUARE_API_CLIENT_SECRET'], \
             app.config['FOURSQUARE_API_VERSION'], self.search_latitude, self.search_longitude, self.search_name )

            print "--- Foursquare Venue Search API Url via lat long: \r", url
            r = requests.get(url)
            venues_json = r.json()


        #Extract relevant attributes from the datum:
        self.venues = []
        for venue in venues_json['response']['venues']:
            v = FoursquareVenue()

            #!!! Shoud get more than one category...
            if len(venue['categories']) > 0:
                v.categories = venue['categories'][0]['name']

            v.foursquare_id = venue['id']
            v.foursquare_url = 'https://foursquare.com/v/' + v.foursquare_id
            v.name = venue['name']
            v.latitude = venue['location']['lat']
            v.longitude = venue['location']['lng']

            self.venues.append(v)


        #print "--- First Venue Returned: ", self.venues[0].name
        #return jsonify({'venues': venues})

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
    __table_args__ = {'mysql_charset': 'utf8'}



class UserPage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'))

    is_hidden  = db.Column(db.Boolean(), default=False)                                      
    is_starred = db.Column(db.Boolean(), default=False)                                      

    added_dt  = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_dt  = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    __table_args__ = {'mysql_charset': 'utf8'}

    UniqueConstraint('user_id', 'page_id', name='user_page_constraint')

    def __init__(self, user_id, page_id):
        self.user_id = user_id
        self.page_id = page_id
        self.id = None

    def __repr__(self):
        return '<UserPage %r>' % self.id

    def insert(self):
        try:
            db.session.add(self)
            db.session.commit()
            print "--- inserted user venue:", self.id
        except Exception as e:
            print "Could not insert user page: ", self.id, e.message, e.args

    def find(self):
        try: 
            #!!! Is this the right way to query?
            up = UserPage.query.filter_by(page_id = self.page_id, user_id = self.user_id).first()
            self.id = up.id
            return self
        except Exception as e:
            print "No existing userpage found by searching for user_id %s and page_id %s" % (self.user_id, self.page_id) 
            return self


class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'))

    source  = db.Column(db.String(50))
    source_url  = db.Column(db.String(512))
    source_title  = db.Column(db.String(255))

    location = db.relationship('Location', backref='page_location', uselist=False)

    notes = db.relationship('PageNote', backref='page', lazy='dynamic')
    user_page = db.relationship('UserPage', backref='user_page', uselist=False)


    added_dt  = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_dt  = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    __table_args__ = {'mysql_charset': 'utf8'}


    #alter table location add column parent_category varchar(50) after reviews;
    def __init__(self, source, source_url, source_title):
        self.source = source
        self.source_url = source_url
        self.source_title = source_title

        self.id = None
        self.location_id = None

    def __repr__(self):
        return '<Page %r>' % self.source_url

    def insert(self):
        try:
            db.session.add(self)
            db.session.commit()
            print "--- inserted page id: %s, source_title: '%s'" % (self.id, self.source_title)
        except Exception as e:
            print "Could not insert page: ", self.source_url, e.message, e.args

    def find(self):
        if self.source_url:
            try: 
                #!!! Is this the right way to query?
                p = Page.query.filter_by(source_url = self.source_url).first()
                self.id = p.id
                return self
            except Exception as e:
                print "No existing page found by searching for source_url: %s" % (self.source_url) 
                return self
        else:
            print "No source_url to search against. Add one first: %s" % (self.source_url) 
            return self


class PageNote(db.Model):                                                                       
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    page_id  = db.Column(db.Integer, db.ForeignKey('page.id'))
    note  = db.Column(db.String(2048))

    user = db.relationship('User', backref='page_note', lazy='joined')
    
    added_dt  = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_dt  = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    UniqueConstraint('note', 'location_id', name='note_location_constraint')
    __table_args__ = {'mysql_charset': 'utf8'}


    def __init__(self, note, user_id):
        self.user_id = user_id
        self.note = note

    def __repr__(self):
        return '<User %r>' % self.note

    def insert(self):
        try:
            db.session.add(self)
            db.session.commit()
            print "--- inserted page_note id %s, note: %s" % (self.id, self.note)
        except Exception as e:
            print "Could not insert page_note user_id: %s note: %s" % (self.user_id, self.note[:50])
            print e.message, e.args

    def find(self):
        if self.note and self.page_id:
            try: 
                #!!! Is this the right way to query?
                pn = PageNote.query.filter_by(page_id = self.page_id, note = self.note).first()
                self.id = pn.id
                return self
            except Exception as e:
                print "No existing page_note found by searching for page_id %s and note: %s" % (self.page_id, self.note) 
                return self
        else:
            print "No page_id / note to search against. Add one first."
            return self

#!!! Rename to Venue Note
class Note(db.Model):                                                               #!!! Rename to Venue Notes        
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    venue_id  = db.Column(db.Integer, db.ForeignKey('venue.id'))
    note  = db.Column(db.String(2048))
    source_url  = db.Column(db.String(512))

    #!!! source  = db.Column(db.String(50))
    #!!! source_title  = db.Column(db.String(255))

    user = db.relationship('User', backref='note', lazy='joined')
    
    added_dt  = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_dt  = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    UniqueConstraint('note', 'venue_id', name='note_venue_constraint')
    __table_args__ = {'mysql_charset': 'utf8'}


    def __init__(self, user_id, note, source_url):
        self.user_id = user_id
        self.note = note
        self.source_url = source_url    
        self.venue_id = None

    def __repr__(self):
        return '<User %r>' % self.note

    def insert(self):
        try:
            db.session.add(self)
            db.session.commit()
            print "--- inserted note id: %s, note: %s" % (self.id, self.note)
        except Exception as e:
            print "Could not insert note: ", self.note[:50], "\r\n", e.message, e.args

#insert into user_venue (user_id,venue_id,is_hidden,is_starred,added_dt,updated_dt) 
#select 2, id, is_hidden,is_starred,added_dt,updated_dt id from venue;
class UserVenue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'))

    is_hidden  = db.Column(db.Boolean(), default=False)                                      
    is_starred = db.Column(db.Boolean(), default=False)                                      

    added_dt  = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_dt  = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    __table_args__ = {'mysql_charset': 'utf8'}

    UniqueConstraint('user_id', 'venue_id', name='user_venue_constraint')

    def __init__(self, user_id, venue_id):
        self.user_id = user_id
        self.venue_id = venue_id

    def __repr__(self):
        return '<UserVenue %r>' % self.id

    def insert(self):
        try:
            db.session.add(self)
            db.session.commit()
            print "--- inserted uservenue id: %s, venue_id: %s user: %s" % (self.id, self.venue_id, self.user_id)
        except Exception as e:
            print "Could not insert user venue venue: ", self.id, e.message, e.args

# ALTER TABLE venue add column is_hidden boolean default false after source_title
# ALTER TABLE venue add column is_starred boolean default false after source_title
class Venue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'))
    name  = db.Column(db.String(255))
    parent_category  = db.Column(db.String(50))

    #!!! remove these
    source  = db.Column(db.String(50))
    source_url  = db.Column(db.String(512))
    source_title  = db.Column(db.String(255))

    foursquare_id = db.Column(db.String(100))
    foursquare_url  = db.Column(db.String(512))
    foursquare_rating  = db.Column(db.String(20))
    foursquare_reviews  = db.Column(db.Integer)
    tripadvisor_id = db.Column(db.String(100))
    tripadvisor_url  = db.Column(db.String(512))
    tripadvisor_rating  = db.Column(db.String(20))
    tripadvisor_reviews  = db.Column(db.Integer)
    yelp_id = db.Column(db.String(100))
    yelp_url  = db.Column(db.String(512))
    yelp_rating  = db.Column(db.String(20))
    yelp_reviews  = db.Column(db.Integer)

    location = db.relationship('Location', backref='venue_location', uselist=False)
    user_venue = db.relationship('UserVenue', backref='user_venue', uselist=False)

    notes = db.relationship('Note', backref='venue', lazy='dynamic')
    categories = db.relationship('VenueCategory', backref='venue', lazy='dynamic')

    added_dt  = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_dt  = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    __table_args__ = {'mysql_charset': 'utf8'}

    #!!! not sure if this is working with sqlite...
    UniqueConstraint('name', 'foursquare_id', name='name_fs_constraint')
    UniqueConstraint('name', 'tripadvisor_id', name='name_yp_constraint')
    UniqueConstraint('name', 'yelp_id', name='name_ta_constraint')

    #!!! parent category
    #alter table location add column parent_category varchar(50) after reviews;
    def __init__(self, name, source, source_url, source_title):
        self.name = name
        self.source = source
        self.source_url = source_url
        self.source_title = source_title
        self.foursquare_id = None
        self.tripadvisor_id = None
        self.yelp_id = None


    def __repr__(self):
        return '<Venue %r>' % self.name

    def insert(self):
        try:
            db.session.add(self)
            db.session.commit()
            print "--- inserted venue:", self.name
        except Exception as e:
            print "Could not insert venue: ", self.name, e.message, e.args


    #!!! simplify this code, lots of repeat methods
    @classmethod
    def get(cls, **kwargs):
        if kwargs['foursquare_id']:
            try: 
                print '--- Searching for venue using foursquare_id: %s' % (kwargs['foursquare_id'])
                ven = Venue.query.filter_by(foursquare_id = kwargs['foursquare_id']).first()
                if ven:
                    print 'Found venue id: %s, name: %s' % (ven.name, ven.id)
                return ven
            except Exception as e:
                print "No existing venue found by searching for foursquare_id: %s" % (kwargs['foursquare_id']) 
        if kwargs['yelp_id']:
            try: 
                print '--- Searching for venue using yelp_id: %s' % (kwargs['yelp_id'])
                ven = Venue.query.filter_by(yelp_id = kwargs['yelp_id']).first()
                if ven:
                    print 'Found venue id: %s, name: %s' % (ven.name, ven.id)
                return ven
            except Exception as e:
                print "No existing venue found by searching for yelp_id: %s" % (kwargs['yelp_id']) 
        if kwargs['tripadvisor_id']:
            try: 
                print '--- Searching for venue using tripadvisor_id: %s' % (kwargs['tripadvisor_id'])
                ven = Venue.query.filter_by(tripadvisor_id = kwargs['tripadvisor_id']).first()
                if ven:
                    print 'Found venue id: %s, name: %s' % (ven.name, ven.id)
                return ven
            except Exception as e:
                print "No existing venue found by searching for tripadvisor_id: %s" % (kwargs['tripadvisor_id']) 
        if kwargs['name']:
            try: 
                print '--- Searching for venue using name: %s' % (kwargs['name'])
                ven = Venue.query.filter_by(name = kwargs['name']).first()
                if ven:
                    print 'Found venue id: %s, name: %s' % (ven.name, ven.id)
                return ven
            except Exception as e:
                print "No existing venue found by searching for name: %s" % (kwargs['name']) 
                #print ven
        print "--- Could not find existing venue"
        return False


class VenueCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    venue_id  = db.Column(db.Integer, db.ForeignKey('venue.id'))
    category = db.Column(db.String(255))
    __table_args__ = {'mysql_charset': 'utf8'}

    def __init__(self, venue_id, category):
        self.venue_id = venue_id
        self.category = category

    def __repr__(self):
        return '<VenueCategory %r>' % self.category

    def insert(self):
        try:
            db.session.add(self)
            db.session.commit()
            print "--- inserted venue_category: %s, %s" % (category, venue_id   )
        except Exception as e:
            print "Could not insert venue-category: ", self.name, e.message, e.args


"""
class VenueParent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<VenueParent %r>' % self.name
"""


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



