#!/usr/bin/env python
# -*- coding: utf-8 -*-

import warnings
from flask.exthook import ExtDeprecationWarning
warnings.simplefilter('ignore', ExtDeprecationWarning)
#import sqlite3
import urllib
import os
import random
import requests
import requests.packages.urllib3
import re
from fuzzywuzzy import fuzz
from datetime import datetime
from json import dumps
from flask_user import login_required, UserManager, UserMixin, SQLAlchemyAdapter, current_user
from flask_mail import Mail
#from contextlib import closing #from werkzeug.utils import secure_filename #requests.packages.urllib3.disable_warnings()
from sqlalchemy import UniqueConstraint, distinct, func
from sqlalchemy.exc import IntegrityError
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, render_template_string, flash, jsonify, make_response
#from flaskext.mysql import MySQL
#import MySQLdb

if(os.environ["NOMNOMTES_ENVIRONMENT"] == 'local'):
    from nomnotes import app
elif(os.environ["NOMNOMTES_ENVIRONMENT"] == 'pythonanywhere'):
    from app import app

from models import db, User, Note, Venue, Location, VenueCategory, FoursquareVenue, FoursquareVenues, UserVenue, UserPage, Page, PageNote

db_adapter = SQLAlchemyAdapter(db, User)        # Register the User model
user_manager = UserManager(db_adapter, app)     # Initialize Flask-User
mail = Mail(app)  

# ----------------------------------------------------------------------------
# Page Note

@app.route('/deletepagenote/id/<int:id>', methods=['GET'])
@login_required 
def delete_page_note(id):
    sql = 'delete from page_note where id = "%s"' % (id)
    db.session.execute(sql)
    db.session.commit()

    initialize_session_vars()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/editpagenote', methods=['POST'])
@login_required 
def edit_page_note():
    if request.method == 'POST':
        #note = urllib.unquote_plus(request.form.get('note'))
        note = request.form.get('note')
        note_id = request.form.get('note_id')
        page_id = request.form.get('page_id')
        print note

    sql = 'update page_note set note = "%s" where id = "%s"' % (note, note_id)
    db.session.execute(sql)
    db.session.commit()

    return jsonify(note_id = note_id, page_id = page_id, note = note)


#This function is used to update a location on a page note 
@app.route('/updatepagelocation', methods=['POST'])
@login_required 
def update_page_location():

    initialize_session_vars()

    location_id = request.form.get('location_id', None)
    page_id = request.form.get('page_id', None)
    print "--- Updating Page Location for page_id %s and location_id %s" % (page_id, location_id)

    #Find Existing Location and Attributes using city and country
    searched_location = Location.query.filter_by(id = location_id).first()
    print "--- Found city: %s" % (searched_location.city)

    new_location = Location ('page', searched_location.city, None, None)
    new_location.country  = searched_location.country

    #Now set the lat long and insert the location
    new_location.set_lat_lng_state_from_city_country()
    new_location.insert()

    #Associate the new location with the page_note
    sql = 'update page set location_id = %s where id = "%s"' % (new_location.id, page_id)
    db.session.execute(sql)
    db.session.commit()

    return redirect(url_for('show_notes', username=session['username']))

# ----------------------------------------------------------------------------
# Note

@app.route('/deletenote/id/<int:id>', methods=['GET'])
@login_required 
def delete_note(id):
    sql = 'delete from note where id = "%s"' % (id)
    db.session.execute(sql)
    db.session.commit()

    initialize_session_vars()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/editnote', methods=['POST'])
@login_required 
def edit_note():
    if request.method == 'POST':
        note = urllib.unquote(request.form.get('note'))
        note = note
        note_id = request.form.get('note_id')
        venue_id = request.form.get('venue_id')

    sql = 'update note set note = "%s" where id = "%s"' % (note, note_id)
    db.session.execute(sql)
    db.session.commit()

    return jsonify(note_id = note_id, venue_id = venue_id, note = note)


@app.route('/addnote', methods=['POST', 'GET'])
def add_note():

    print '-' * 80

    """ 
    When an end user highlights a selection and saves to Nom Notes when not on a review page from tripadvisor, foursquare, or yelp,
    this part of the code is executed. Next step will be to save the highlight to the following:
    - page_note
    - user_page (if the page has not been saved by this user)
    - page      (if the page has not been saved before by any user)
    - location  (if the page has not been saved before by any user, we'll try to find the city or country that the page refers to)
    """


    if request.method == 'POST' and request.form.get('action')   == 'new_page_note_from_home':

        pn = PageNote(
            urllib.unquote(request.form.get('note', None)), 
            session['user_id'], 
        )
        pn.source = 'nomnotes'
        pn.page_id = request.form.get('page_id', None)
        pn.insert()

        return jsonify(note_id = pn.id, page_id = pn.page_id, note = pn.note)


    elif request.method == 'POST' and request.form.get('action')   == 'new_venue_note_from_home':

        n = Note(
            session['user_id'], 
            urllib.unquote(request.form.get('note', None)), 
            'http://nomnotes'
        )
        n.source = 'nomnotes'
        n.venue_id = request.form.get('venue_id', None)
        n.insert()

        return jsonify(note_id = n.id, venue_id = n.venue_id, note = n.note)


    elif request.method == 'POST' and request.form.get('action') == 'new_venue_note_from_venue':

        # Parameters from post request
        # ---------------------------------------------------------
        print "--- Processing parameters from the addnote/ post request for venue:"

        user_id = session['user_id']
        source_url = request.form.get('page_url', None)
        source_id = request.form.get('source_id', None)
        source = request.form.get('source', None)


        v = Venue(
            request.form.get('name', None), 
            source,
            source_url,
            request.form.get('page_title', None),
        )

        l = Location(
            'venue', 
            request.form.get('city', None),
            request.form.get('latitude', None),     #Note: Yelp doesn't supply lat/long
            request.form.get('longitude', None)
        )

        n = Note(user_id, 
            request.form.get('note', None), 
            source_url
        )

        categoriesStr = request.form['categories']
        categories = categoriesStr.split(",")
        v.parent_category = classify_parent_category(categories, v.name.split())
        l.address1 = None #!!!
        l.address2 = None #!!!

        # Save data depending on the review source
        # ---------------------------------------------------------
        print "--- Determining source of the note and calling respective apis to supplement data. Source: ", source

        if source == 'foursquare':

            #Venue Attributes
            if request.form.get('rating', None):
                v.foursquare_rating = request.form.get('rating', None)
            if request.form.get('reviews', None):
                v.foursquare_reviews = request.form.get('reviews', None)
            v.foursquare_url = source_url
            v.foursquare_id = source_id

            #Location Attributes, acquired from foursquare venue api
            #fsv = FoursquareVenue()
            #fsv.get(v.foursquare_id, l.latitude, l.longitude)
            #l.city = fsv.city               #Use city, state, and country from the api rather than from the forms for consistency
            #l.state = fsv.state
            #l.country = fsv.country

        elif source == 'tripadvisor' or source == 'yelp':

            #Set source specific properties:
            setattr(v, source + "_rating", request.form.get('rating', None))
            setattr(v, source + "_reviews", request.form.get('reviews', None))
            setattr(v, source + "_url", source_url)
            setattr(v, source + "_id", source_id)

            #Call the Foursquare API and find the venue in the provided city
            #Use that data to supplement venue data
            fsvs = FoursquareVenues(v.name, l.city, l.latitude, l.longitude)
            fsvs.search()

            # Find a matching venue from a set of venues returned from foursquare
            # Choose the one that has the closest matching name
            fsv = None
            for fsvenue in fsvs.venues:
                fuzzy_match_score = fuzz.token_sort_ratio(v.name, fsvenue.name)
                print "Venue Match Ratio: %s. Source: [%s] Foursquare: [%s]" % (fuzzy_match_score, v.name, fsvenue.name)

                if fuzzy_match_score > 80:
                    fsv = fsvenue
                    break
            
            if fsv:
                v.name = fsv.name
                v.foursquare_id = fsv.foursquare_id
                v.foursquare_url = fsv.foursquare_url

                #Call FS Venue API to Get FS Ratings/Reviews, since ratings/reviews aren't available in search
                fsven = FoursquareVenue()
                fsven.get(v.foursquare_id, l.latitude, l.longitude)
                v.foursquare_rating = fsven.rating
                v.foursquare_reviews = fsven.reviews

                #If no category derived from source, use foursquare categories and venue categories:
                if len(categories) == 0:
                    print "--- Using Foursquare venue api category: ", fsv.categories
                    categories = fsv.categories
                    v.parent_category = classify_parent_category(categories, v.name.split())
                #if fsv.city:
                #    l.city = fsv.city
                #l.state = fsv.state
                #l.country = fsv.country

                # yelp pages dont show lat/long, override with foursquare api
                if not l.latitude:
                    l.latitude = fsv.latitude       
                if not l.longitude:
                    l.longitude = fsv.longitude

            else:
                print "No matching foursquare venue could be found via the api."
                
        else: 
            print "--- Source is not yelp, tripadvisor, of foursquare... "
            #Next sources to add: Google Maps and Facebook

        #Call the Google API to derive consistent city | state | country from lat long for all sources
        l.set_city_state_country_with_lat_lng_from_google_location_api()


        # Insert note and other dimensions
        # ---------------------------------------------------------
        print "--- Inserting note as well as venue and location, if applicable"

        # Search If the venue exists, just add the note


        searched_venue_in_db = Venue.get(name=v.name, foursquare_id=v.foursquare_id, tripadvisor_id=v.tripadvisor_id, yelp_id=v.yelp_id)
        if searched_venue_in_db:
            #Insert User Venue Map
            uv = UserVenue(user_id, searched_venue_in_db.id)
            uv.insert()

            #Insert Note
            n.venue_id = searched_venue_in_db.id
            n.insert()

            return "Added to Nom Notes: " + n.note

        # If no venue exists, add the location, then venue, then venue categories, then note
        else:
            #Add location
            l.insert()

            #Add venue
            v.location_id = l.id
            v.insert()

            #Insert User Venue Map
            uv = UserVenue(user_id, v.id)
            uv.insert()
            
            #Insert the categories for the venue
            for category in categories:
                vc = VenueCategory(v.id, category)
                vc.insert

            #Insert note
            n.venue_id = v.id
            n.insert()

            return "Added to Nom Notes: " + n.note        


    elif request.method == 'POST' and request.form.get('action') == 'new_page_note_from_other_page':

        print "--- Processing parameters from the addnote/ post request for other pages:"


        pn = PageNote(
            urllib.unquote(request.form.get('note', '')), 
            session['user_id']
        )

        p = Page(
            request.form.get('source', None),
            request.form.get('page_url', None),
            request.form.get('page_title', None)
        )

        print "--- Checking to see if page exists. If not, insert it"
        p.find()
        if not p.id:
            print "--- Attempting to derive location of the page from the title."

            #Attempt to find the location in free-form text. Tokenize the page title and match against existing cities and countries:
            title_tokens = p.source_title.split(" ");

            cities = db.session.execute("select distinct city, country from location where city is not null and country is not null")
            #countries = db.session.execute("select distinct country from location")

            location_note_city = None
            location_note_country = None
            found_city = False


            for row in cities:
                for token in title_tokens:
                    match_score = fuzz.token_sort_ratio(token.lower(), row['city'].lower())
                    if(match_score >= 90):
                        location_note_city = row['city']
                        location_note_country = row['country']
                        print "Found city in title: %s, %s" % (location_note_city, location_note_country)
                        found_city = True
                        break
                if found_city:
                    break
                #for country in countries:
                #    if(token.lower() == country['country'].lower()):
                #        location_note_country = country['country']


            #Find google location based on the city/country. Then insert it
            if location_note_city and location_note_country:
                l = Location(
                        'page', 
                        location_note_city, 
                        None, 
                        None
                    )
                l.country = location_note_country
                l.set_lat_lng_state_from_city_country()

                print "--- Inserting location "
                l.insert()

                if l.id:
                    p.location_id = l.id
                    "--- Associating new location to page"

            print "--- Inserting page: "
            p.insert()

        print "--- Checking to see if page note exists. If not, insert it"
        pn.page_id = p.id
        pn.find()
        if not pn.id:
            pn.insert()

        print "--- Checking if user_page mapping exists. If not, insert it"
        up = UserPage(session['user_id'], pn.page_id)
        up.find()
        if not up.id:
            up.insert()

        return jsonify(page_note_id = pn.id, page_id = p.id, note = pn.note, msg = "Inserted note: %s" % pn.note )


    
    
    #!!! return json instead
    return "No Note Added =("

# ----------------------------------------------------------------------------
# Helper Functions for Note Dimensions

@app.route('/updateparentcategory', methods=['GET'])
def update_parent_category():

    #Get all locations
    locations = Location.query

    #Update each parent category if the classification is new or doesn't exist
    for row in locations:
        #Reclassify the the parent category 

        #Transform category dictionary into a list
        category_list = []
        for i, item in enumerate(row.categories):
            #print '~' * 50
            #print item.category, i
            #print '~' * 50
            category_list.append(item.category) 

        new_parent_category_classification = classify_parent_category(category_list)
        if(new_parent_category_classification != row.parent_category):
            new_parent_category = new_parent_category_classification
            sql = 'update venue set parent_category = "%s" where id = "%s"' % (new_parent_category, row.id)
            db.session.execute(sql)
            db.session.commit()
            print "--- Changed category for %s from %s to %s" % (row.name, row.parent_category, new_parent_category)

    #!!! return json instead
    return "done"


def classify_parent_category(category_list, name_tokens):

    print "--- Classifying venue.parent_category. Using existing categories (%s) and venue name %s" % (category_list, name_tokens)
    places = ['theater', 'park', 'museum', 'garden', 'club', 'plaza', 'beach', \
              'palace', 'cove','bay','cave', 'lookout', 'boat', 'fortress']
    coffees = ['coffee', 'caf']
    foods = ['breakfast', 'italian', 'restaurant', 'mediterranean', 'european', 'seafood' \
             'bakery', 'bakeries', 'pizza', 'ice cream', 'bar', 'pub', 'cocktail' \
             'donut', 'food', 'ice cream', 'dessert', 'sandwich']

    parent_category = None

    #Try to classify the category based on the categories scraped from the page
    for category in category_list:
        for food in foods:
            if category.lower().find(food) >= 0:
                return 'food'
        for place in places:
            if category.lower().find(place) >= 0:
                return 'place'
        for coffee in coffees:
            if category.lower().find(coffee) >= 0:
                return 'coffee'

    #If unsuccessful, try to classify the category based on the venue name, examining each token for a match
    for token in name_tokens:
        for food in foods:
            if token.lower().find(food) >= 0:
                return 'food'
        for place in places:
            if token.lower().find(place) >= 0:
                return 'place'
        for coffee in coffees:
            if token.lower().find(coffee) >= 0:
                return 'coffee'

    return 'unknown'


@app.route('/findcityinstring', methods=['POST'])
def find_city_in_string():

    if request.method == 'POST' and request.form.get('string', None):
        #Persist variables posted via the form to venues_result_set variables
        string = request.form['string']
        string_tokens = string.split(" ");
        cities = db.session.execute("select distinct city from location")
        for city in cities:
            for token in string_tokens:
                if(token.lower() == city['city'].lower()):
                    return city['city']
    return 'No city match'

# ----------------------------------------------------------------------------
# Page

@app.route('/deletepage/id/<int:id>', methods=['GET'])
@login_required 
def delete_page(id):

    sql = 'delete from page_note where page_id = %s' % (id)
    db.session.execute(sql)
    db.session.commit()

    sql = 'delete from user_page where page_id = %s and user_id= %s ' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()

    initialize_session_vars()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/unstarpage/id/<int:id>', methods=['GET'])
@login_required  
def unstar_page(id):
    initialize_session_vars()

    sql = 'update user_page set is_starred = 0 where page_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/starpage/id/<int:id>', methods=['GET'])
@login_required 
def star_page(id):
    initialize_session_vars()

    sql = 'update user_page set is_starred = 1 where page_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/hidepage/id/<int:id>', methods=['GET'])
@login_required 
def hide_page(id):
    initialize_session_vars()

    sql = 'update user_page set is_hidden = True where page_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    return redirect(url_for('show_notes', username=session['username']))

#!!! showvenue working?
@app.route('/showpage/id/<int:id>', methods=['GET'])
@login_required 
def show_page(id):
    initialize_session_vars()

    sql = 'update user_page set is_hidden = False where page_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    
    return redirect(url_for('show_notes', username=session['username']))

# ----------------------------------------------------------------------------
# Venue

@app.route('/deletevenue/id/<int:id>', methods=['GET'])
@login_required 
def delete_venue(id):

    sql = 'delete from note where venue_id = %s' % (id)
    db.session.execute(sql)
    db.session.commit()

    sql = 'delete from user_venue where venue_id = %s and user_id= %s ' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()

    initialize_session_vars()
    return redirect(url_for('show_notes', username=session['username']))


@app.route('/unstarvenue/id/<int:id>', methods=['GET'])
@login_required 
def unstar_venue(id):
    initialize_session_vars()

    sql = 'update user_venue set is_starred = 0 where venue_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/starvenue/id/<int:id>', methods=['GET'])
@login_required 
def star_venue(id):
    initialize_session_vars()

    sql = 'update user_venue set is_starred = 1 where venue_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    return redirect(url_for('show_notes', username=session['username']))

@app.route('/hidevenue/id/<int:id>', methods=['GET'])
@login_required 
def hide_venue(id):
    initialize_session_vars()

    sql = 'update user_venue set is_hidden = True where venue_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    return redirect(url_for('show_notes', username=session['username']))

#!!! showvenue working?
@app.route('/showvenue/id/<int:id>', methods=['GET'])
@login_required 
def show_venues(id):
    initialize_session_vars()

    sql = 'update user_venue set is_hidden = False where venue_id = %s and user_id=%s' % (id, session['user_id'])
    db.session.execute(sql)
    db.session.commit()
    
    return redirect(url_for('show_notes', username=session['username']))


# ----------------------------------------------------------------------------
# Admin and Database 


@app.route('/nnadmin', methods=['GET'])
#!!! @login_required 
def show_admin_pages():
     return render_template('show_admin.html')


@app.route('/createtables')
#!!! @login_required 
def create_tables(): 

    User.__table__.create(db.session.bind, checkfirst=True)

    Location.__table__.create(db.session.bind, checkfirst=True)

    Venue.__table__.create(db.session.bind, checkfirst=True)
    VenueCategory.__table__.create(db.session.bind, checkfirst=True)
    UserVenue.__table__.create(db.session.bind, checkfirst=True)

    Note.__table__.create(db.session.bind, checkfirst=True)
    
    Page.__table__.create(db.session.bind, checkfirst=True)
    PageNote.__table__.create(db.session.bind, checkfirst=True)
    UserPage.__table__.create(db.session.bind, checkfirst=True)

    #db.session.execute.create_all()
    return "created tables"


@app.route('/droptables')
#!!! @login_required 
def drop_tables(): 

    Note.__table__.drop(db.session.bind, checkfirst=True)
    VenueCategory.__table__.drop(db.session.bind, checkfirst=True)
    UserVenue.__table__.drop(db.session.bind, checkfirst=True)
    Venue.__table__.drop(db.session.bind, checkfirst=True)

    PageNote.__table__.drop(db.session.bind, checkfirst=True)
    UserPage.__table__.drop(db.session.bind, checkfirst=True)
    Page.__table__.drop(db.session.bind, checkfirst=True)

    Location.__table__.drop(db.session.bind, checkfirst=True)
    User.__table__.drop(db.session.bind, checkfirst=True)

    db.session.commit()

    #create_database()    
    return "dropped tables"


@app.route('/truncatetables')
#!!! @login_required 
def truncate_tables(): 
    #db.session.execute("delete from user where id >= 1")
    db.session.execute("delete from note where id >= 1")
    db.session.execute("delete from venue_category where id >= 1")
    db.session.execute("delete from venue where id >= 1")
    db.session.execute("delete from user_venue where user_id >= 1 or location_id >= 1")

    db.session.execute("delete from location where id >= 1")

    db.session.execute("delete from page_note where id >= 1")
    db.session.execute("delete from user_page where id >= 1")
    db.session.execute("delete from page where id >= 1")

    db.session.commit()

    return "truncated dbs"

"""
def query_db(db, query, args=(), one=False):
    cur = db.execute(query)
    r = [dict((cur.description[i][0], value) for i, value in enumerate(row)) for row in cur.fetchall()]
    #cur.connection.close()
    return (r[0] if r else None) if one else r
"""

# ----------------------------------------------------------------------------
# Controllers / Views

@app.route('/cities', methods=['GET'])
def get_cities():

    q = request.args.get('q', None)
    test = request.args.get('test', None)

    #!!! add user
    if q:
        where_filter = "where city like '%" + q + "%' and city is not null"
    else:
        where_filter = "where city is not null"


    
    sql = "select city, max(id) id from location %s group by city" % (where_filter);
    print sql
    cities_result_set = db.session.execute(sql)

    city = {}
    cities = []
    for row in cities_result_set:
        print row.city
        city = {}
        city['id'] = row.id
        city['city'] = row.city
        city['tokens'] = row.city.split(" ");
        cities.append(city)
    
    #return cities
    return jsonify(cities)

def get_pages_without_location():
    initialize_session_vars()

    #!!! remove me
    session['page_user_id'] = 2

    #!!! Move to model
    page_notes_result_set = Page.query.join(UserPage) \
                            .filter(UserPage.user_id == session['page_user_id'], Page.location_id == None) \
                            .order_by(Page.id.desc())

    pages =[]
    for row in page_notes_result_set:
        item = dict(
             id=row.id,
             source_url=row.source_url, 
             source_title=row.source_title, 
             is_starred=row.user_page.is_starred
        )
        pages.append(item) 

    return pages


@app.route('/pages', methods=['GET'])
def get_pages_with_notes():
    initialize_session_vars()

    #Query Venues, apply filters
    #!!! Move to model
    page_notes_result_set = Page.query.join(Location).join(UserPage) \
                            .filter(PageNote.user_id == session['page_user_id']) \
                            .order_by(UserPage.is_starred.desc(),Page.id.asc())

    # If city is filtered, find the lat/long of the first item in that city and return all other 
    # locations within zoom miles from it
    if session['city'] != '':
        l = Location.query.filter_by(city = session['city']).first()
        latitude_start = l.latitude
        longitude_start = l.longitude
        zoom = session['zoom']

        sql = "SELECT id, SQRT( \
                POW(69.1 * (latitude - %s), 2) + \
                POW(69.1 * (%s - longitude) * COS(latitude / 57.3), 2)) AS distance \
                FROM location \
                GROUP BY id \
                HAVING SQRT( \
                POW(69.1 * (latitude - %s), 2) + \
                POW(69.1 * (%s - longitude) * COS(latitude / 57.3), 2)) < %s" \
                % (latitude_start, longitude_start, latitude_start, longitude_start, session['zoom'])

        locations = db.session.execute(sql)
        locationIDs = []
        for location in locations:
            locationIDs.append(location.id)
        page_notes_result_set = page_notes_result_set.filter( (Location.id.in_(locationIDs)) | (Location.city == session['city']))
        

    if session['country'] != '':
        print "~~~ filtered country:", session['country']
        page_notes_result_set = page_notes_result_set.filter(Location.country == session['country'])
    if session['is_hidden'] != '':
        print "~~~ is_hidden:", session['is_hidden']
        page_notes_result_set = page_notes_result_set.filter(UserVenue.is_hidden == False)

    #print page_notes_result_set;


    pages =[]
    for row in page_notes_result_set:
        notes_array = []
        for note_row in row.notes:
            item = dict(
                note = note_row.note,
                id = note_row.id
                )
            notes_array.append(item)
        #!!! convert rating from string to float
        item = dict(
             notes=notes_array, 
             id=row.id,
             source_url=row.source_url, 
             source_title=row.source_title, 
             latitude=row.location.latitude, 
             longitude=row.location.longitude,
             city=row.location.city,
             country=row.location.country,
             source=row.source,
             is_starred=row.user_page.is_starred
        )
        pages.append(item) 

    return pages

@app.route('/venues', methods=['GET'])
def get_venues_with_notes():
    initialize_session_vars()

    #Query Venues, apply filters
    #!!! Move to model
    venues_result_set = Venue.query.join(Location).join(UserVenue) \
                            .filter(Note.user_id == session['page_user_id']) \
                            .order_by(UserVenue.is_starred.desc(),Venue.name.asc())

    # If city is filtered, find the lat/long of the first item in that city and return all other 
    # locations within zoom miles from it
    if session['city'] != '':
        l = Location.query.filter_by(city = session['city']).first()
        latitude_start = l.latitude
        longitude_start = l.longitude
        zoom = session['zoom']

        sql = "SELECT id, SQRT( \
                POW(69.1 * (latitude - %s), 2) + \
                POW(69.1 * (%s - longitude) * COS(latitude / 57.3), 2)) AS distance \
                FROM location \
                GROUP BY id \
                HAVING SQRT( \
                POW(69.1 * (latitude - %s), 2) + \
                POW(69.1 * (%s - longitude) * COS(latitude / 57.3), 2)) < %s" \
                % (latitude_start, longitude_start, latitude_start, longitude_start, session['zoom'])

        locations = db.session.execute(sql)
        locationIDs = []
        for location in locations:
            locationIDs.append(location.id)
        venues_result_set = venues_result_set.filter(Location.id.in_(locationIDs))

    if session['country'] != '':
        print "~~~ filtered country:", session['country']
        venues_result_set = venues_result_set.filter(Location.country == session['country'])
    if session['parent_category'] != '':
        print "~~~ parent category:", session['parent_category']
        venues_result_set = venues_result_set.filter(Venue.parent_category == session['parent_category'])
    if session['is_hidden'] != '':
        print "~~~ is_hidden:", session['is_hidden']
        venues_result_set = venues_result_set.filter(UserVenue.is_hidden == False)
    
    #print '-'*50
    #print "--- Get Venue SQL: \r\n", venues_result_set


    venues =[]
    for row in venues_result_set:

        notes_array = []
        for note_row in row.notes:
            item = dict(
                note = note_row.note,
                id = note_row.id
                )
            notes_array.append(item)
        #!!! convert rating from string to float
        item = dict(
             notes=notes_array, 
             id=row.id,
             name=row.name, 
             parent_category=row.parent_category, 
             source_url=row.source_url, 
             latitude=row.location.latitude, 
             longitude=row.location.longitude,
             city=row.location.city,
             state=row.location.state,
             country=row.location.country,
             source=row.source,
             foursquare_reviews=row.foursquare_reviews,
             foursquare_rating=str_to_float(row.foursquare_rating), 
             foursquare_url=row.foursquare_url,
             tripadvisor_reviews=row.tripadvisor_reviews,
             tripadvisor_rating=str_to_float(row.tripadvisor_rating),
             tripadvisor_url=row.tripadvisor_url,
             yelp_reviews=row.yelp_reviews,
             yelp_rating=str_to_float(row.yelp_rating),
             yelp_url=row.yelp_url,
             is_starred=row.user_venue.is_starred

        )

        venues.append(item) 


    #Google Maps Requires the response to have a particular format
    #!!! fix this
    if request.method == 'GET':
        format = request.args.get("format")
        if format == 'js':
            markers = dict({'markers':venues})
            return make_response("gmapfeed(" + dumps(markers) + ");")

    return venues



@app.route('/updatevenuecategories', methods=['GET'])
def update_venue_categories():
    initialize_session_vars()

    sql = "update venue \
    set parent_category = 'place' \
    where parent_category = 'unknown' \
      and tripadvisor_url like '%sAttraction_Review%s'" % ('%','%')
    db.session.execute(sql)
    db.session.commit()

    sql = "update venue \
    set parent_category = 'food' \
    where parent_category = 'unknown' \
      and tripadvisor_url like '%sRestaurant_Review%s'" % ('%','%')
    db.session.execute(sql)
    db.session.commit()

    sql = "update venue \
    set parent_category = 'food' \
    where parent_category = 'coffee'"
    db.session.execute(sql)
    db.session.commit()

    return redirect(url_for('show_notes', username=session['username']))



@app.route('/', methods=['GET'])
def redirect_to_username_homepage():
    initialize_session_vars()
    return redirect(url_for('show_notes', username=session['username']))
    #return redirect(url_for('show_notes'))
    #return redirect("/profile/" + session['username'])


@app.route('/profile/<username>', methods=['GET'])
def show_notes(username):



    #Get Session Filters and Convert them for use with sql where statements
    session['username'] = username
    initialize_session_vars()

    #Get Venues, Pages, and Pages without a location (for location categorization)
    venues = get_venues_with_notes()
    pages  = get_pages_with_notes()
    pages_no_loc = get_pages_without_location()


    #Unique Cities, limited by existing selections
    #!!! move to model
    city_sql = "select distinct city \
           from venue v \
             inner join user_venue uv on v.id = uv.venue_id \
             inner join location l on l.id = v.location_id \
           where uv.user_id=%s and city is not null" % (session['page_user_id'])
    for key in session:
        if key == 'country' or key == 'parent_category' or key == 'is_hidden':
            if session[key] != '':
                city_sql = city_sql + " and %s='%s' " % (key, session[key])
    cities = db.session.execute(city_sql)


    #Unique Countries, limited by existing selections
    #!!! move to model
    state_sql = "select distinct country \
           from venue v \
             inner join user_venue uv on v.id = uv.venue_id \
             inner join location l on l.id = v.location_id \
           where uv.user_id=%s and city is not null" % (session['page_user_id'])
    countries = db.session.execute(state_sql)


    #Unique Categories, limited by existing selections
    #!!! add user id, move to model
    parent_category_sql = "select distinct parent_category \
           from venue v \
             inner join user_venue uv on v.id = uv.venue_id \
             inner join location l on l.id = v.location_id \
           where uv.user_id=%s and city is not null" % (session['page_user_id'])
    for key in session:
        if key == 'country' or key == 'is_hidden' or key == 'city':
            if session[key] != '':
                parent_category_sql = parent_category_sql + " and %s='%s' " % (key, session[key])
    parent_category_sql = parent_category_sql + " order by parent_category asc"                
    parent_categories = db.session.execute(parent_category_sql)


    #User
    page_user = User.query.filter_by(id = session['page_user_id']).first()


    #Shareable url
    session['share_url'] = "%s/profile/%s?" % (app.config['HOSTNAME'],session['username'])
    for key in session:
        if key == 'city' or key == 'country' or key == 'parent_category' or key == 'is_hidden' or key == 'zoom':
            if session[key] != '':
                session['share_url'] = session['share_url'] + "%s=%s&" % (key,session[key])
    session['share_url'] = session['share_url'][:-1]



    return render_template('show_notes.html', venues=venues, pages=pages, pages_no_loc=pages_no_loc, \
                            cities=cities, countries=countries, \
                            parent_categories=parent_categories, user=page_user)
    #return dumps(locations_json)


def initialize_session_vars():

    if request.args.get('zoom'):
        session['zoom'] = request.args.get('zoom')
    if not ('zoom' in session):
        session['zoom'] = 5
    session['zoom_options'] = ['1', '3', '5','10','25','50']

    """
    The following statements process the location and category filters.
    For a given filter, first set the session variable based on the form.
    If the form says reset, set the session variable to empty set.
    Then create a where statement
    """


    #!!! Controls whether a user can edit a page based on whether they are logged inner
    #!!! This is probably not the right way to do this...
    if 'user_id' in session:
        if not 'username' in session:
            u = User.query.filter_by(user_id = session['user_id']).first()
            session['username'] = u.username
            session['can_edit'] = 1
            session['page_user_id'] = session['user_id']
        else: 
            u = User.query.filter_by(username = session['username']).first()
            session['page_user_id'] = session['user_id']
            if u.id == int(session['user_id']):
                session['can_edit'] = 1
            else:
                session['can_edit'] = 0
    else:
        session['can_edit'] = 0
        if 'username' in session:
            u = User.query.filter_by(username = session['username']).first()

            if u.id:
                session['page_user_id'] = u.id
            else:
                #!!! Future iteration: redirect to localhost
                session['page_user_id'] = 'almostvindiesel'





    #if username and the user_id is the same, then 

    #If user


    if request.args.get('is_hidden'):
        print "is hidden: ", request.args.get('is_hidden')
        if request.args.get('is_hidden') == 'showhidden':
            session['is_hidden'] = ''
        elif request.args.get('is_hidden') == ' ':
            session['is_hidden'] = 0
    else:
        session['is_hidden'] = 0

    if request.args.get('parent_category'):
        session['parent_category'] = request.args.get('parent_category')
    if  not ('parent_category' in session) or session['parent_category'] == 'reset' or session['parent_category'] == '':
        session['parent_category'] = ''

    if request.args.get('city'):
        session['city'] = request.args.get('city')
    if not 'city' in session or session['city'] == 'reset' or session['city'] == '':
        session['city'] = ''
    
    if request.args.get('country'):
        session['country'] = request.args.get('country')
        session['city'] = ''
    if not 'country' in session or session['country'] == 'reset' or session['country'] == '':
        session['country'] = ''



def str_to_float(str):
    if not str:
        str = 0
        str = float(str)
        str = None;
    else:
        str = float(str.strip())

    return str

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

