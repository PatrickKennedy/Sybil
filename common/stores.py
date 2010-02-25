#!/usr/bin/env python
#
#  Sybil - Python Profile Manager
#  Copyright (c) 2008, Patrick Kennedy
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions
#  are met:
#
#  - Redistributions of source code must retain the above copyright
#  notice, this list of conditions and the following disclaimer.
#
#  - Redistributions in binary form must reproduce the above copyright
#  notice, this list of conditions and the following disclaimer in the
#  documentation and/or other materials provided with the distribution.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE FOUNDATION OR
#  CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
#  EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
#  PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
#  LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
#  NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
import uuid
import datetime
import time
from common.stores import UUIDTest

u = uuid.uuid4()
u2 = uuid.uuid4()
t = UUIDTest.get_or_insert(
    uuid=u,
    key_name=UUIDTest._get_key_name(str(now)))
t2 = UUIDTest.get_or_insert(
    uuid=u2,
    key_name=UUIDTest._get_key_name(str(datetime.datetime.now())))

print "t == t2 ->", t == t2
print t._get_key_name(t.created), t2._get_key_name(t2.created)
print "t.key_name == t2.key_name ->", t.key_name == t2.key_name
print t.created, '\n', t2.created
print t.key().name()
print t2.key().name()
print t.key().name() == t2.key().name()

t.delete()
t2.delete()
"""

import datetime
import logging
import os
import time
import urllib
import uuid

from google.appengine.datastore.entity_pb import EntityProto
from google.appengine.ext import db
from google.appengine.api import users, memcache, apiproxy_stub_map
from django.utils.html import escape

import common
from common import const, counter, utils

from lib import search

auto_memo_entities = ['Profile', 'UserData', 'World']

def model_name_from_key(key):
    return key.path().element_list()[0].type()

def auto_unmemo(service, call, request, response):
	if call == "Put":
		logging.info("Entity List: %s\n" % request.entity_list())
		for entity in request.entity_list():
			if isinstance(entity, EntityProto) or\
				model_name_from_key(entity.key()) not in auto_memo_entities:
				continue
			key_name = str(entity.key().name())
			cache_keys = ['%s:%s' % (prefix, key) for prefix in entity._memo_prefixes]
			memcache.delete_multi(cache_keys)

	elif call == "Delete":
		for entity in request.key_list():
			if model_name_from_key(entity.key()) not in auto_memo_entities:
				continue
			key_name = str(entity.key().name())
			cache_keys = ['%s:%s' % (prefix, key) for prefix in entity._memo_prefixes]
			memcache.delete_multi(cache_keys)

#apiproxy_stub_map.apiproxy.GetPostCallHooks().Append("auto_unmemo", auto_unmemo)

class UUIDProperty(db.Property):
	data_type = uuid.UUID
	datastore_type = uuid.UUID

	# For writing to datastore.
	def get_value_for_datastore(self, model):
		uuid_ = super(self.__class__, self).get_value_for_datastore(model)
		return str(uuid_)

	# For reading from datastore.
	def make_value_from_datastore(self, value):
		if value is None:
			return None
		return uuid.UUID(value)

class ModelBase(object):
	_memo_prefixes = []
	_url_patterns = {
		'user': '/%s/',
		'profile': '/%s/%s/',
		'world': '/world/%s/',
	}

	@classmethod
	def _key_from_path(cls, key_name, *parents):
		return db.Key.from_path(cls.__name__, key_name, *parents)

	@property
	def key_name(self):
		return self.key().name()

class ModelCaching(object):
	"""

	Provide convience functions for caching entities.

	"""

	@staticmethod
	def __fill_blanks(keys, results):
		"""
		
		Work around the fact memcache.get_multi() doesn't return None for
		non-existant keys and the fact dicts are unsorted.
		
		Return a list in the same order as they original key_names from
		memcache.get_multi()'s dictionary, filling in "blanks" with None.
		
		"""
		return [results.get(key, None) for key in keys]

	@classmethod
	def get_by_key_name(cls, key_names, parent=None):
		# We need to perseve the return value if the input is a list
		# other wise we need to return just the entity itself.
		is_list = True
		# memcache.get_mutli() only accepts lists.
		if not isinstance(key_names, list):
			is_list = False
			key_names = [key_names]
		
		r = cls.__fill_blanks(key_names, memcache.get_multi(key_names))
		r = utils.deserialize_models(r)
		
		if not [x for x in r if x is not None]:
			r = super(ModelCaching, cls).get_by_key_name(key_names, parent)
			if r:
				logging.info("CACHING GET")
				if isinstance(r, db.Model):
					#logging.info('CACHING: %s' % r.key_name)
					memcache.set(r.key_name, utils.serialize_models(r))
				else:
					memcache.set_multi(dict([(x.key_name, utils.serialize_models(x)) for x in r if x]))
		return r if is_list else r[0]

	def put(self, *args, **kwargs):
		"""put(*args, **kwargs) -> None

		Set the object in the cache and clear the object's various caches
		before every put() call.

		Returns whatever put() returns.

		"""
		# We need to put() the instance to set the key before we can act on it.
		r = super(ModelCaching, self).put(*args, **kwargs)
		#logging.info("CACHING PUT")
		memcache.set(self.key_name, utils.serialize_models(self))
		cache_keys = ['%s:%s' % (x, self.key_name) for x in self._memo_prefixes]
		memcache.delete_multi(cache_keys)

		return r

	def delete(self, *args, **kwargs):
		# We need to get the key before the instance is deleted.
		cache_keys = ['%s:%s' % (x, self.key_name) for x in self._memo_prefixes]
		cache_keys.insert(0, self.key_name)
		memcache.delete_multi(cache_keys)

		return super(ModelCaching, self).delete(*args, **kwargs)

	@classmethod
	def load(cls, key_name, query_logic={}, cache=True):
		"""

		Hits the memcache and then the datastore to load an entity.

		"""

		#if cache:
		#	cache_key = '%s:%s' % (cls.__name__.lower(), key_name)
		#	data = memcache.get(cache_key)
		#	if data:
		#		return data

		# If it's not in there we'll try getting it from the key_name
		# This should work in virtually every case.
		data = cls.get_by_key_name(key_name)

		# That didn't work -- let's do a gql query.
		if not data and query_logic:
			q = cls.all()
			for key, value in query_logic.items():
				q.filter(key, value)
			data = q.get()

		if data:
			memcache.set(cache_key, data)

		return data


class UserData(db.Expando, ModelCaching, ModelBase):
	"""

	Sybil's user data storage.

	key_names are of the form:
		'user.user_id'
	This permanently ties them to the user's Google account.

	"""

	user	= db.UserProperty()
	joined	= db.DateTimeProperty(auto_now_add=True)
	last_seen	= db.DateTimeProperty(auto_now=True)
	nickname	= db.StringProperty(default='')
	unix_nick	= db.StringProperty(default='')
	theme		= db.StringProperty(default='framed')
	design		= db.StringProperty(default='original')

	custom_css		= db.TextProperty(default='')
	use_custom_css	= db.BooleanProperty(default=False)

	cf_script		= db.StringProperty(default='daze')
	use_custom_cf	= db.BooleanProperty(default=False)
	custom_cf_script	= db.TextProperty(default='')

	ga_code	= db.StringProperty(default='')

	# Any memcache
	_memo_prefixes = ['nickpointer']
	key_name_form = '%s'

	def user_id(self):
		return self.user.user_id()

	@property
	def url(self):
		return self._url_patterns['user'] % self.nickname

	#@property
	#def nickname(self):
	#	return self.nickname if self._nickname else self.user.nickname

	@classmethod
	def load(cls, user=None):
		"""

		Gets the user's stored data from the database. If no user data exists a
		new entry will be created.

		"""

		# If no user is passed, attempt to use the currently logged in user.
		# If nobody is logged in, return None
		if not user:
			user = users.get_current_user()
			if not user:
				return None

		key_name = "%s" % user.user_id()

		# Start out with the key_name. get_by_key_name should hit the
		# transparent cache.
		data = cls.get_by_key_name(key_name)

		# That didn't work -- let's do a gql query, just in case the user's
		# email address changed but we can find it by object
		if not data:
			query = UserData.all()
			query.filter('user =', user)
			data = query.get()

		# Ok, so there is nothing in the database yet. We assume that we can
		# create a new entry, using the key from above.
		if not data:
			data = cls.get_or_insert(key_name, user=user)

		return data

	@property
	def url(self):
		return self._url_patterns['user'] % self.nickname

	#@property
	#def nickname(self):
	#	return self.nickname if self._nickname else self.user.nickname

	@classmethod
	def load_from_nickname(cls, nick):
		"""Utility Function to UserData"""

		unix_nick = utils.unix_string(nick)
		data = memcache.get("nickpointer:%s" % unix_nick)
		if not data:
			data = UserData.all().filter("unix_nick =", unix_nick).get()
			if data:
				memcache.set("nickpointer:%s" % unix_nick, data)

		return data


class Profile(search.Searchable, ModelCaching, db.Expando, ModelBase):
	"""

	A Profile is the primary storage unit in Sybil.

	It's key_name should be of the form:
		'p:profile.unix_name;author.key_name'
	Which, unfortunately, means name changes are anything but simple (as all
	connections and comments will be tied to the key_name).

	Bulk actions performed on profiles should be part of a speedy task queue.

	"""

	author		= db.ReferenceProperty(UserData)
	created		= db.DateTimeProperty(auto_now_add=False)
	# updated does't auto_now because scheme updates murder this number
	updated		= db.DateTimeProperty(auto_now=False)
	public		= db.BooleanProperty(default=True)
	markup		= db.StringProperty(default="ReST", choices=["ReST", "Textile", "PlainText"])
	word_count	= db.IntegerProperty(default=0)

	name		= db.StringProperty(required=True)
	unix_name	= db.StringProperty(required=True)
	age			= db.StringProperty(default='')
	gender		= db.StringProperty(choices=['Male', 'Female', 'Neither'], default='')
	race		= db.StringProperty(default='')
	height		= db.StringProperty(default='')
	weight		= db.StringProperty(default='')
	apperence 	= db.TextProperty(default='')
	background	= db.TextProperty(default='')
	extra_info	= db.TextProperty(default='')
	links		= db.TextProperty(default='')
	common		= db.TextProperty(default='')

	INDEX_ONLY = [
		'name', 'age', 'gender', 'race', 'height', 'weight',
		'apperence', 'background', 'extra_info', 'links',
	]
	INDEX_TITLE_FROM_PROP = 'name'

	_memo_prefixes = ['markup']
	key_name_form = 'p:%s:%s'

	@property
	def url(self):
		return "/%s/%s/" % (self.author.nickname, self.unix_name)

	@property
	def edit_url(self):
		return self.url + 'edit/'

	@property
	def delete_url(self):
		return self.url + 'delete/'

	def page_admin(self, user):
		return (user == self.author.user)

	def in_world(self, world):
		key_name = WorldConnection.key_name_form % (world.key_name, self.key_name)
		return bool(WorldConnection.get_by_key_name(key_name))

class World(search.Searchable, ModelCaching, db.Expando, ModelBase):
	"""

	Worlds store extra background information and link Profiles together.

	A World's key_name should be of the form:
		'w:world.unix_name'

	"""

	author		= db.ReferenceProperty(UserData)
	name		= db.StringProperty(required=True)
	unix_name	= db.StringProperty(required=True)
	created	= db.DateTimeProperty(auto_now_add=False)

	about	= db.TextProperty(default='')
	links	= db.TextProperty(default='')
	common	= db.TextProperty(default='')
	# If a world is public it means anyone can view it.
	public	= db.BooleanProperty(default=False)
	# If a world is open it means anyone can post to it.
	open	= db.BooleanProperty(default=False)
	markup	= db.StringProperty(default="Textile", choices=["ReST", "Textile", "PlainText"])

	INDEX_ONLY = [
		'name', 'about', 'links',
	]
	INDEX_TITLE_FROM_PROP = 'name'

	_memo_prefixes = ['markup']
	key_name_form = 'w:%s'

	@property
	def url(self):
		return "/world/%s/" % self.unix_name

	@property
	def edit_url(self):
		return self.url + '?action=edit'

	@property
	def delete_url(self):
		return self.url + '?action=delete'

	def user_can_view(self, udata):
		"""user_can_view(udata: UserData) -> bool

		Return True if `udata` is a member of the world
		or if the world is public.

		"""

		if self.public:
			return True
		if not udata:
			return False

		key_name = WorldMember.key_name_form % (self.key_name, user.key_name)
		return bool(WorldMember.get_by_key_name(key_name))

	def user_can_post(self, udata):
		"""user_can_post(udata: UserData) -> bool

		Return True if `udata` is a member of the world
		or if the world is both open and public.

		"""

		if not udata:
			return False
		if (self.author == udata) or (self.open and self.public):
			return True

		key_name = WorldMember.key_name_form % (self.key_name, udata.key_name)
		return bool(WorldMember.get_by_key_name(key_name))

class WorldMember(db.Model):
	"""

	Defines a connection between a world and a user.

	WorldMembership key_names should be of the format:
		'wm:world.key_name;udata.key_name'

	"""
	world	= db.ReferenceProperty(World, required=True)
	user	= db.ReferenceProperty(UserData, required=True)
	key_name_form = 'wm:%s:%s'

class WorldConnection(db.Model):
	"""

	Defines a connection between a world and a profile.
	A WorldConnections key_name should be of the format:
		'wc:world.key_name;profile.key_name'
	This format allows for speedy look ups on a profile's inclusion in a world.

	As a rule of thumb a speedy task queue should be used to delete several of a
	user's profile connections (for example when a user leaves a world).

	"""
	world	= db.ReferenceProperty(World, required=True)
	profile	= db.ReferenceProperty(Profile, required=True)
	key_name_form = 'wc:%s:%s'

class Timeline(db.Expando):
	"""Container for specific events."""
	name	= db.StringProperty(default='')
	
class Event(db.Expando):
	"""Contains information regarding a specific event in time."""

class HostDummy(db.Model):
	"""Contains functions."""

class Comment(db.Expando, ModelBase):
	"""DynComments is an experimental single comment system.

	The Expando class only accepts a list of predefined types, so Entity keys
	have to be used instead of a reference to an Entity.
	Note: Fetching works the same.

	"""

	author	= db.ReferenceProperty(UserData)
	body	= db.TextProperty(default='')
	html_body = db.TextProperty(default='')
	markup	= db.StringProperty(default="ReST", choices=["ReST", "Textile", "PlainText"])
	created	= db.DateTimeProperty(auto_now_add=True)
	updated	= db.DateTimeProperty(auto_now=True)

	@property
	def host_(self):
		return db.get(self.host)

	def get_host_url(self):
		host = db.get(self.host)
		return host.url

	def get_host_name(self):
		"""get_host_name() -> str

		Return an escaped version of the host name.

		"""

		host = db.get(self.host)
		return escape(host.name)

class MessageFactory(object):
	@staticmethod
	def from_comment(recipient, comment, perma=False):
		"""Message.make_new_comment(recipient: *, comment: Comment) -> Message

		Return a fully formed comment message.

		"""
		message = Message(
			author=comment.author,
			recipient=recipient,

		)
		if perma:
			import framework

			context = {
				'comment': comment,
			}

			message.body 		= framework.TemplateRenderer(['message', 'newcomment'], context).render()
			message.permanent	= True
		else:
			message.base		= comment.key()
			message.base_type	= 'comment'
		return message

	@staticmethod
	def gen_user_joined_world(recipients, member, author):
		"""Message.make_new_comment(recipient: *, member: WorldMember) -> Message

		Generate a fully formed member joined message for every user in recipient.

		"""


		import framework

		context = {
			'user': member.user,
			'world': member.world,
			'author': author,
		}

		renderer = framework.TemplateRenderer(['message', 'userjoinedworld'], context)

		for r in recipients:
			yield MessageFactory.perma_message(r.user, author, renderer)

	@staticmethod
	def gen_user_left_world(recipients, member, author):
		"""Message.make_new_comment(recipient: *, member: WorldMember) -> Message

		Generate a fully formed member left message for every user in recipient.

		"""

		import framework

		context = {
			'user': member.user,
			'world': member.world,
			'author_owns': author == member.user,
			'author': author,
		}

		renderer = framework.TemplateRenderer(['message', 'userleftworld'], context)

		for r in recipients:
			yield MessageFactory.perma_message(r.user, author, renderer)

	@staticmethod
	def gen_profile_joined_world(recipients, conn, author):
		import framework

		context = {
			'user': author,
			'profile': conn.profile,
			'world': conn.world,
			'author': author,
		}

		renderer = framework.TemplateRenderer(['message', 'profilejoinedworld'], context)

		for r in recipients:
			yield MessageFactory.perma_message(r.user, author, renderer)

	@staticmethod
	def gen_profile_left_world(recipients, conn, author):
		import framework

		context = {
			'user': conn.user,
			'profile': conn.profile,
			'world': conn.world,
			'author': author,
		}

		renderer = framework.TemplateRenderer(['message', 'profileleftworld'], context)

		for r in recipients:
			yield MessageFactory.perma_message(r.user, author, renderer)


	@staticmethod
	def perma_message(recipient, author=None, renderer=None):
		"""Message.perma_message(
			recipient:UserData,
			author:UserData=None,
			renderer:TemplateRenderer
		) -> Message

		Return a fully formed message using the passed TemplateRenderer for the body.

		"""

		message = Message()
		message.author = (author or recipient)
		message.recipient = recipient
		message.body = renderer.render()
		return message


	@staticmethod
	def make_new_comment(comment, recipient):
		"""Message.make_new_comment(comment: Comment, recipient: *) -> Message

		Return a fully formed comment message.

		"""

		try:
			assert isinstance(comment, CommentBase), 'Attemped to create a new comment notification with %r.' % comment
		except AssertionError, e:
			logging.exception(e)
			return None
		host_url = comment.get_host_url()
		name = host = comment.get_host_name()
		if host_url:
			host = '<a href="%s">%s</a>' % (host_url, host)

		if isinstance(recipient, basestring):
			recipient = UserData.load_from_nickname(recipient)

		message = Message(
			author=comment.author,
			recipient=recipient,
			body=comment.body,
			host=host,
		)
		logging.info('Notifying User (%s) of new Comment from User (%s) on Profile (%s)' %
			 (recipient, comment.author, name))
		return message

	@staticmethod
	def make_new_profile(profile, recipient):
		"""Message.make_new_profile(profile: Profile, recipient: *) -> Message

		Return a fully formed new profile notification message.

		"""

		assert isinstance(profile, Profile)
		url = profile.url
		name = profile.name
		host = '<a href="%s">%s</a>' % (url, name)

		recipient = UserData.load_from_nickname(recipient)

		message = Message(
			author=profile.author,
			recipient=recipient,
			body="New profile",
			host=host,
		)
		logging.info('Notifying User (%s) of new Profile (%s) from User (%s)' %
					 (recipient, name, profile.author))
		return message

	@staticmethod
	def make_add_to_world(conn, recipient):
		"""Message.make_add_to_world(conn: WorldConnection, recipient: *) -> Message

		Return a fully formed profile added to world notification message.

		"""

		assert isinstance(conn, WorldConnection)
		world_url = conn.world.url
		world_name = conn.world.name
		host = '<a href="%s">%s</a>' % (world_url, world_name)
		profile_url = conn.profile.url
		profile_name = conn.profile.name
		profile_host = '<a href="%s">%s</a>' % (profile_url, profile_name)

		recipient = UserData.load_from_nickname(recipient)

		message = Message(
			author=profile.author,
			recipient=recipient,
			body='Profile (%s) added to world' % profile_host,
			host=host,
		)
		logging.info('Notifying User (%s) of new Profile (%s) from User (%s)' %
					 (recipient, name, profile.author))
		return message


class Message(db.Expando, ModelBase):
	"""Storage for a single message

	Properties
		author:		The user who invoked an action which generated the message.
		recipient:	The user to whom the message is for.
		body:		A prerendered version of the message which overrides
						rendering a template. Used for permanent messages.
		template:	The name of a template file in ./templates/messages/
						Templates assume the message has all required variables.
		created:	DateTime the message was created.


	"""
	author		= db.ReferenceProperty(UserData,
		collection_name='message_author_set')
	recipient	= db.ReferenceProperty(UserData,
		collection_name='message_recipient_set')
	body		= db.TextProperty(default='')
	template	= db.StringProperty(default='')
	created		= db.DateTimeProperty(auto_now_add=True)

	def put(self, *args, **kwargs):
		"""put(*args, **kwargs) -> None

		Automatic incrementing of the recipient's messages counter.
		This is safe because messages are never put twice.

		Returns whatever put() returns.

		"""
		r = super(self.__class__, self).put(*args, **kwargs)

		c = counter.Counter('%sMessages' % self.recipient.key_name, 2)
		c.increment(1)

		return r

	def delete(self, *args, **kwargs):
		"""delete(*args, **kwargs) -> None

		Automatic deincrementing of the recipient's messages counter.

		Returns whatever delete() returns.

		"""
		r = super(self.__class__, self).delete(*args, **kwargs)

		c = counter.Counter('%sMessages' % self.recipient.key_name, 2)
		c.increment(-1)

		return r

	@property
	def user_url(self):
		return self.get_url(self.author.nickname)

	def get_host_name(self):
		if self.profile:
			return self.profile.name
		elif self.world:
			return self.world.name

	def get_host_url(self):
		if self.profile:
			return self.profile.url
		elif self.world:
			return self.world.url
