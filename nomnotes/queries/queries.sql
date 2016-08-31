select
  uv.user_id, 
  v.name,
  l.city,
  uv.is_hidden,
  note
from venue v
  left join location l on v.location_id = l.id
  left join user_venue uv on v.id = uv.venue_id
  left join note n on n.venue_id = v.id
where 1=1
  and v.id = 86
;


-- Deletions
delete from note where id = 320;
delete from user_venue where id in (94,95,96)


-- Basic Selects
select id, name from venue order by id desc limit 5;
select id, left(n.note, 20) note from note n order by id desc limit 5;


-- Basic Selects, Where Statement
select id, name, foursquare_id, tripadvisor_id, yelp_id
from venue 
where id = 81


select id, left(n.note, 20) note from note n order by id desc limit 5;

select
  pn.id page_note_id,
  p.id page_id,
  l.id location_id,
  l.city,
  p.source_title
from page_note pn
  inner join page p on pn.page_id = p.id
  left join location l on p.location_id = l.id
;

select 
  uv.venue_id,
  count(uv.venue_id) v
from user_venue uv 
group by 1;





select
  n.id note_id,
  left(n.note, 20) note,
  l.id location_id,
  v.id note_id,
  v.name venue,
  uv.user_id user_id,
  uv.id uv_key,
  uv.venue_id uvvenue_id,
  v.foursquare_id fs_id,
  v.tripadvisor_id ta_id,
  v.yelp_id y_id,
  l.latitude,
  l.longitude,
  l.city
from note n
  left join venue v on v.id = n.venue_id
  left join user_venue uv on v.id = uv.venue_id
  left join location l on v.location_id = l.id
where n.id in (328,276)
;


user
user_page

page
page_note

user_venue
venue
venue_category

location
