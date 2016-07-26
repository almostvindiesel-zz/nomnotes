import sqlite3
import os
import random
import requests
import requests.packages.urllib3
#import jsonify
from datetime import datetime
from json import dumps
#from flask_sqlalchemy import SQLAlchemy
from flask_user import login_required, UserManager, UserMixin, SQLAlchemyAdapter
from flask_mail import Mail
#from contextlib import closing
#from werkzeug.utils import secure_filename
#requests.packages.urllib3.disable_warnings()
from sqlalchemy import UniqueConstraint, distinct, func
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, render_template_string, flash, jsonify, make_response
from sqlalchemy.exc import IntegrityError
from flaskext.mysql import MySQL
import MySQLdb

if(os.environ["NOMNOMTES_ENVIRONMENT"] == 'local'):
    from nomnotes import app
elif(os.environ["NOMNOMTES_ENVIRONMENT"] == 'pythonanywhere'):
    from app import app

from models import User, Note, Location, LocationCategory, LocationParent, SavedUrl, db


db_adapter = SQLAlchemyAdapter(db, User)        # Register the User model
user_manager = UserManager(db_adapter, app)     # Initialize Flask-User
mail = Mail(app)  

@app.route('/addnote', methods=['POST'])
def add_note():

    #!!! add more conditions to fail gracefully
    if request.method == 'POST':

        user_id = session['user_id']
        note = request.form['note']
        source = find_source_based_on_url(request.form['page_url'])
        name = request.form['name']
        latitude = request.form['latitude']
        longitude = request.form['longitude']
        city = request.form['city']
        country = '' # !!! 
        parent_id = 0 # !!!
        page_url = request.form['page_url']
        page_title = request.form['page_title']

        rank = '' # !!! 
        rating = request.form['rating']
        reviews = request.form['reviews'].replace(',', '')
        categoriesStr = request.form['categories']
        categories = categoriesStr.split(",")
        #print categories
        #return "donezo"
        #updated_dt = datetime.utcnow
        #updated_dt = datetime.utcnow()
        #added_dt = updated_dt

        # If the location exists, just add the note
        if (get_location(name, source)):
            location_id = get_location(name, source)
            #update_location()
            #update_categories()

            n = Note(user_id, location_id, note, page_url)
            db.session.add(n)
            db.session.commit()

        # If no location exists, add the location and then add the note
        else:
            #print '*' * 50
            #print added_dt
            #print '*' * 50
            parent_category = classify_parent_category(categories)


            l = Location(parent_id, name, source, latitude, \
                         longitude, city, page_url, page_title, \
                         rank, rating, reviews)
            db.session.add(l)
            db.session.commit()


            #insert_location_category()
            location_id = get_location(name, source)
            insert_categories_into_db(location_id,categories)
            print "New Location Id is " + str(location_id)

            n = Note(user_id, location_id, note, page_url)
            db.session.add(n)
            db.session.commit()

        return "added note: " + note
    else:
        return "no note added"


@app.route('/updateparentcategory', methods=['GET'])
def update_parent_category():

    #Get all locations
    locations = Location.query

    #Update each parent category if the classification is new or doesn't exist
    for row in locations:
        #Reclassify the the parent category 
        new_parent_category_classification = classify_parent_category(row.categories)
        if(new_parent_category_classification != row.parent_category):
            new_parent_category = new_parent_category_classification
            sql = 'update location set parent_category = "%s" where id = "%s"' % (new_parent_category, row.id)
            db.session.execute(sql)
            db.session.commit()
            print "Changed category for %s from %s to %s" % (row.name, row.parent_category, new_parent_category)

    return "done"


def classify_parent_category(categories):
    for datum in categories:
        print '-'*50
        print datum.category
        if datum.category.lower().find("theater") >= 0:
            return 'place'
        elif datum.category.lower().find("park") >= 0:
            return 'place'
        elif datum.category.lower().find("museum") >= 0:
            return 'place'
        elif datum.category.lower().find("garden") >= 0:
            return 'place'
        elif datum.category.lower().find("club") >= 0:
            return 'place'
        elif datum.category.lower().find("plaza") >= 0:
            return 'place'
        elif datum.category.lower().find("restaurant") >= 0:
            return 'food'
        elif datum.category.lower().find("coffee") >= 0:
            return 'coffee'
        elif datum.category.lower().find("Caf") >= 0:
            return 'coffee'
        elif datum.category.lower().find("breakfast") >= 0:
            return 'food'
        elif datum.category.lower().find("bakery") >= 0:
            return 'food'
        elif datum.category.lower().find("pizza") >= 0:
            return 'food'
        elif datum.category.lower().find("ice cream") >= 0:
            return 'food'
        elif datum.category.lower().find("bar") >= 0:
            return 'food'
        elif datum.category.lower().find("pub") >= 0:
            return 'food'
        elif datum.category.lower().find("cocktail") >= 0:
            return 'food'
        elif datum.category.lower().find("donut") >= 0:
            return 'food'
        elif datum.category.lower().find("food") >= 0:
            return 'food'
        elif datum.category.lower().find("place") >= 0:
            return 'food'
    return 'unknown'

# This method adds a web page into the url table
# !!! I may have fucked this up when updateding other functions...
@app.route('/addurl', methods=['POST'])
def add_url():
    # !!! Add some logic to redirect the user to a page to login if not logged in

    if request.method == 'POST' and request.form.get('url', None):
        #Persist variables posted via the form to locations_result_set variables
        title = request.form['title']
        url = request.form['url']
        user_id = session['user_id']
        country = " " # !!! add later

        #Try to automatically dedect the city of the location by seeing if the title of the page contains the city.
        #Otherwise, default to no city
        title_tokens = title.split(" ");
        saved_url_city = ''
        cities = db.session.execute("select distinct city from location")
        for city in cities:
            for token in title_tokens:
                if(token.lower() == city['city'].lower()):
                    saved_url_city = city['city']

        #Write Saved URL to database
        su = SavedUrl(user_id, url, title, saved_url_city, country)
        db.session.add(su)
        db.session.commit()
        msg = "URL Saved %s (%s)" % (title, su.id)
        print msg
        return msg

    else:
        msg = 'WARNING: no saved_url record added to the database'
        print msg
        return msg 


def get_location(name, source):        
    try:
        sql = "select id from location where name ='%s' and source='%s' limit 1" % (name, source)
        loc = db.session.execute(sql)
        for row in loc:
            location_id = row['id']
            return location_id
    except Exception, err:
        print 'ERROR from get_location function, could not get location_id', err
        return False
    return False


def find_source_based_on_url(page_url):
    if page_url.find('tripadvisor') >= 0:
        return 'tripadvisor'
    elif page_url.find('foursquare') >= 0:
        return 'foursquare'
    elif page_url.find('yelp') >= 0:
        return 'yelp'
    else: 
        return 'unknown'


def insert_categories_into_db(location_id,categories): 
    #Loop through all categories and insert them individually into the database.
    #Possible to reform this to create one insert statement for the future
    
   for category in categories: 
        try:
            lc = LocationCategory(location_id, category)
            db.session.add(lc)
            db.session.commit()
            print "new record added with location_id: %s category: %s" % (location_id, category)
        except IntegrityError as e:
            print 'Integrity Error: ', e


@app.route('/createdb')
def create_database(): 

    Location.__table__.create(db.session.bind, checkfirst=True)
    LocationParent.__table__.create(db.session.bind, checkfirst=True)
    LocationCategory.__table__.create(db.session.bind, checkfirst=True)
    User.__table__.create(db.session.bind, checkfirst=True)
    Note.__table__.create(db.session.bind, checkfirst=True)
    SavedUrl.__table__.create(db.session.bind, checkfirst=True)

    #db.session.execute.create_all()

    return "created tables"


@app.route('/dropandcreatedb')
def drop_and_createdb(): 
    db.session.execute("drop table if exists saved_url")
    db.session.execute("drop table if exists note")
    db.session.execute("drop table if exists user")
    db.session.execute("drop table if exists location_category")
    db.session.execute("drop table if exists location_parent")
    db.session.execute("drop table if exists location")
    create_database()    
    return "drop and created all dbs"


@app.route('/truncatedb')
def truncate_note_database(): 
    db.session.execute("delete from user where id >= 1")
    db.session.execute("delete from note where id >= 1")
    db.session.execute("delete from location where id >= 1")
    db.session.execute("delete from location_category where id >= 1")
    db.session.execute("delete from location_parent where id >= 1")
    db.session.execute("delete from saved_url where id >= 1")
    db.session.commit()
    return redirect(url_for('show_notes'))


def query_db(db, query, args=(), one=False):
    cur = db.execute(query)
    r = [dict((cur.description[i][0], value) for i, value in enumerate(row)) for row in cur.fetchall()]
    #cur.connection.close()
    return (r[0] if r else None) if one else r


def initialize_session_vars():
    if not ('city' in session):
        session['city'] = ''
    if not ('parent_category' in session):
        session['parent_category'] = ''

    if request.method == 'GET':
        if request.args.get("parent_category"):
            session['parent_category'] = request.args.get("parent_category")
            if session['parent_category'] == 'reset':   
                session['parent_category'] = ''
        if request.args.get('city'):
            session['city'] = request.args.get('city')
            if session['city'] == 'reset':
                session['city'] = ''

    session['hostname'] = app.config['HOSTNAME']


@app.route('/', methods=['GET'])
@login_required 
def homepage_redirect():
    return redirect(url_for('show_notes'))


@app.route('/nnadmin', methods=['GET'])
@login_required 
def show_admin_pages():

     return render_template('show_admin.html')




@app.route('/notes', methods=['GET'])
@login_required 
def show_notes():


    #Get Session Filters and Convert them for use with sql where statements
    initialize_session_vars()

    #Query the locations, locations_category, and notes tables filtered by city and or category
    #and return a json blob to be used to display the data table and google map
    if session['parent_category'] and session['city']:
        locations_result_set = Location.query.filter(Location.parent_category == session['parent_category'], Location.city == session['city'])
    elif session['parent_category']:
        locations_result_set = Location.query.filter(Location.parent_category == session['parent_category'])
    elif session['city']:
        locations_result_set = Location.query.filter_by(city = session['city'])
    else:
        locations_result_set = Location.query

    locations_json =[]
    for row in locations_result_set:
        notes_array = []
        for note_row in row.notes:
            notes_array.append(note_row.note)
        item = dict(
             name=row.name, 
             parent_category=row.parent_category, 
             notes=notes_array, 
             page_url=row.page_url, 
             latitude=row.latitude, 
             longitude=row.longitude,
             city=row.city,
             source=row.source,
             reviews=row.reviews,
             rating=row.rating
        )
        locations_json.append(item) 


    #Google Maps Requires the response to have a particular format
    if request.method == 'GET':
        format = request.args.get("format")
        if format == 'js':
            markers = dict({'markers':locations_json})
            return make_response("gmapfeed(" + dumps(markers) + ");")

    ##########################################################################################

    #!!! Build filters based on the primary attributes: (1) User (2) City (3) Category
    if session['city']:
        where_filter_city =  " and city='" + session['city'] + "' "
    else:
        where_filter_city = ' '

    if session['parent_category']:
        where_filter_category =  " and parent_category='" + session['parent_category'] + "' "
    else:
        where_filter_category = ' '

    #!!! Add user id limit

    #Unique Saved urls
    sql = "select * from saved_url where 1=1 " + where_filter_city
    saved_urls = db.session.execute(sql)

    #Unique Cities, limited by existing selections
    sql = "select distinct city from location l inner join location_category lc on l.id = lc.location_id where 1=1" + where_filter_city +  where_filter_category
    cities = db.session.execute(sql)

    #Unique Categories, limited by existing selections
    sql = "select distinct parent_category from location_category lc inner join location l on l.id = lc.location_id where 1=1" + where_filter_city +  where_filter_category
    parent_categories = db.session.execute(sql)

    #Users !!!
    user = User.query.filter_by(id = session['user_id'])



    return render_template('show_notes.html', locations_json=locations_json, saved_urls=saved_urls, \
                            cities=cities, parent_categories=parent_categories, current_city=session['city'], \
                            current_parent_category=session['parent_category'], user=user[0])
    #return dumps(locations_json)


@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

