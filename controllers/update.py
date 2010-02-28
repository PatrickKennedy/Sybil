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

import	datetime
import	logging
import	os
import	random
import	sys
import	urllib
import	wsgiref.handlers
import	sys

from	google.appengine.api		import users, memcache
from	google.appengine.ext		import gql, db
from	google.appengine.ext		import webapp
from	google.appengine.ext.webapp	import template

from	common			import counter, framework, stores, utils
from	common.stores	import UserData
from	common.stores	import Profile, World, Comment, WorldMember

class Index(framework.BaseRequestHandler):

	def get(self, action):
		msg = 'Something really good happened'

		if action == 'error':
			borked.lol
			msg = 'You should never see this'

		elif action == 'flush_cache':
			from google.appengine.api import memcache
			memcache.flush_all()
			msg = "Cache Cleared"

		elif action == 'fix_connections':
			last_key = self.request.get('last_key', None)

			cls = stores.WorldConnection
			if last_key is None:
				# First request, just get the first name out of the datastore.
				obj = cls.gql('ORDER BY __key__').get()
				last_key = str(obj.key())

			last_key = db.Key(last_key)

			q = cls.gql('WHERE __key__ >= :1 ORDER BY __key__', last_key)
			objects = q.fetch(limit=2)
			obj = objects[0]
			if len(objects) == 2:
				next_name = str(objects[1].key())
				next_url = '/update/%s/?last_key=%s' % (action, next_name)
			else:
				next_name = 'FINISHED'
				self.flash.msg = "Connections Fixed"
				next_url = '/'  # Finished processing, go back to main page.
			# In this example, the default values of 0 for num_votes and avg_rating are
			# acceptable, so we don't need to do anything other than call put().
			obj.created = obj.profile.updated
			obj.put()

			self.render_next(cls, last_key, next_name, next_url)
			return

		elif action == 'profile_count':
			from common import counter
			last_key = self.request.get('last_key', None)

			cls = stores.Profile
			if last_key is None:
				# First request, just get the first name out of the datastore.
				obj = cls.gql('ORDER BY __key__').get()
				last_key = str(obj.key())
				# Reset the counters to 0 so we get an accurate count.
				c = counter.Counter('TotalProfiles')
				c.delete()
				#c = counter.Counter('%sProfiles' % obj.author.key_name, 1)
				#c.delete()

			last_key = db.Key(last_key)

			q = cls.gql('WHERE __key__ >= :1 ORDER BY __key__', last_key)
			objects = q.fetch(limit=6)
			if len(objects) == 6:
				next_name = str(objects.pop().key())
				next_url = '/update/%s/?last_key=%s' % (action, next_name)
			else:
				next_name = 'FINISHED'
				self.flash.msg = "Profiles Counted"
				next_url = '/'  # Finished processing, go back to main page.
			# In this example, the default values of 0 for num_votes and avg_rating are
			# acceptable, so we don't need to do anything other than call put().
			for obj in objects:
				c = counter.Counter('TotalProfiles')
				c.increment()
				c = counter.Counter('%sProfiles' % obj.author.key_name, 1)
				c.increment()

			self.render_next(cls, last_key, next_name, next_url)
			return

		elif action == 'world_count':
			from common import counter
			last_key = self.request.get('last_key', None)

			cls = stores.World
			if last_key is None:
				# First request, just get the first name out of the datastore.
				obj = cls.gql('ORDER BY __key__').get()
				last_key = str(obj.key())
				# Reset the counters to 0 so we get an accurate count.
				c = counter.Counter('TotalWorlds')
				c.delete()
				#c = counter.Counter('%sWorlds' % obj.author.key_name, 1)
				#c.delete()

			last_key = db.Key(last_key)

			q = cls.gql('WHERE __key__ >= :1 ORDER BY __key__', last_key)
			objects = q.fetch(limit=6)
			if len(objects) == 6:
				next_name = str(objects.pop().key())
				next_url = '/update/%s/?last_key=%s' % (action, next_name)
			else:
				next_name = 'FINISHED'
				self.flash.msg = "Worlds Counted"
				next_url = '/'  # Finished processing, go back to main page.
			# In this example, the default values of 0 for num_votes and avg_rating are
			# acceptable, so we don't need to do anything other than call put().

			for obj in objects:
				c = counter.Counter('TotalWorlds')
				c.increment()
				c = counter.Counter('%sWorlds' % obj.author.key_name, 1)
				c.increment()

			self.render_next(cls, last_key, next_name, next_url)
			return

		elif action == 'schema':
			from common.stores import UserData
			last_key = self.request.get('last_key', None)

			cls = UserData
			if last_key is None:
				# First request, just get the first name out of the datastore.
				obj = cls.gql('ORDER BY __key__').get()
				last_key = str(obj.key())

			last_key = db.Key(last_key)

			q = cls.gql('WHERE __key__ >= :1 ORDER BY __key__', last_key)
			objects = q.fetch(limit=2)
			obj = objects[0]
			if len(objects) == 2:
				next_name = str(objects[1].key())
				next_url = '/update/%s/?last_key=%s' % (action, next_name)
			else:
				next_name = 'FINISHED'
				self.flash.msg = "%s Schema Updated" % cls.__name__
				next_url = '/'  # Finished processing, go back to main page.
			# In this example, the default values of 0 for num_votes and avg_rating are
			# acceptable, so we don't need to do anything other than call put().
			obj.wave_address = obj.wave_addr
			del obj.wave_addr
			obj.put()

			self.render_next(cls, last_key, next_name, next_url)
			return

		self.flash.msg = msg
		self.redirect('/')

	def render_next(self, cls, name, next_name, next_url):
		context = {
			'obj_name': cls.__name__,
			'current_name': name,
			'next_name': next_name,
			'next_url': next_url,
		}
		t = template.Template("""<html>
<head>
<meta http-equiv="refresh" content="0;url={{ next_url }}"/>
</head>
<body>
<h3>Update {{ obj_name }}</h3>
<ul>
<li>Updated: {{ current_name }}</li>
<li>About to update: {{ next_name }}</li>
</ul>
</body>
</html>""")
		self.response.out.write(t.render(context))


class Count(framework.BaseRequestHandler):
	t = template.Template("""<html>
	<head>
		<meta http-equiv="refresh" content="0;url={{ next_url }}"/>
	</head>
	<body>
		<h3>Counting {{ obj_name }}</h3>
		<ul>
			<li>Counted: {{ current_count }}</li>
		</ul>
	</body>
</html>""")

	def generic_init_logic(self):
		"""Return a seed object to use a key from."""
		return self.counter_data['cls'].gql('ORDER BY __key__').get()

	def generic_query_logic(self, last_key):
		"""Return a query."""
		return self.counter_data['cls'].gql('WHERE __key__ >= :1 ORDER BY __key__', last_key)

	def generic_counter_logic(self, objects):
		"""Incriment the counter using the list of objects retrieved"""
		count = len(objects)
		c = counter.Counter(self.counter_data['counter_name'],
							self.counter_data['counter_shards'])
		c.increment(count)
		return count

	@framework.Lazy
	def counter_data(self):
		return {
			'cls': stores.UserData,
			'limit': 6,
			'counter_name': 'TotalUsers',
			'counter_shards': 5,
			'init_logic': self.generic_init_logic,
			'query_logic': self.generic_query_logic,
			'counter_logic': self.generic_counter_logic,
			'flash_msg': "All Users Counted",
		}

	def get(self, what, where=None):
		what = what.lower()
		self.what = what
		self.where = where
		if not hasattr(self, what):
			self.flash.msg = ('Unknown what (%s).<br/>Common whats: all_profiles, '
							  'user_profiles, world_profiles, etc.' % what)
			self.redirect(self.referer)
			return

		getattr(self, what)(where)

	def render_next(self, count, next_url):
		context = {
			'obj_name': self.what,
			'current_count': count,
			'next_url': next_url,
		}
		self.response.out.write(self.t.render(context))

	def generic_counter(self):
		current_count = self.request.get_range('current_count', 0, default=0)
		last_key = self.request.get('last_key', None)
		next_key = None
		referer = self.request.get('referer', '/')
		cls = self.counter_data['cls']

		if last_key is None:
			# First request, just get the first name out of the datastore.
			obj = self.counter_data['init_logic']()
			last_key = str(obj.key())
			# Reset the counters to 0 so we get an accurate count.
			c = counter.Counter(self.counter_data['counter_name'],
								self.counter_data['counter_shards'])
			c.delete()

		last_key = db.Key(last_key)
		q = self.counter_data['query_logic'](last_key)
		objects = q.fetch(limit=self.counter_data['limit'])
		if len(objects) == self.counter_data['limit']:
			next_key = str(objects.pop().key())

		new_count = self.counter_data['counter_logic'](objects)
		if next_key:
			if self.where:
				next_url = '/update/count/%s/%s/?current_count=%d&last_key=%s&referer=%s' % (
					self.what, self.where, (current_count + new_count), next_key, referer)
			else:
				next_url = '/update/count/%s/?current_count=%d&last_key=%s&referer=%s' % (
					self.what, (current_count + new_count), next_key, referer)
		else:
			next_name = 'FINISHED'
			self.flash.msg = self.counter_data['flash_msg']
			self.flash.msg += " (%d)" % (current_count + new_count)
			next_url = referer

		self.render_next(current_count + new_count, next_url)

	def index_all_profiles(self, what):
		counter_data = self.counter_data
		counter_data['cls'] = stores.Profile
		# We're not putting any entities so we can fetch as many as possible.
		counter_data['limit'] = 1000
		counter_data['flash_msg'] = 'All Profiles Queued to be Indexed'

		def counter_logic(objects):
			[obj.enqueue_indexing(url='/tasks/index/') for obj in objects]
			return len(objects)

		counter_data['counter_logic'] = counter_logic

		self.generic_counter()

	def index_all_worlds(self, what):
		counter_data = self.counter_data
		counter_data['cls'] = stores.World
		# We're not putting any entities so we can fetch as many as possible.
		counter_data['limit'] = 1000
		counter_data['flash_msg'] = 'All Worlds Queued to be Indexed'

		def counter_logic(objects):
			[obj.enqueue_indexing(url='/tasks/index/') for obj in objects]
			return len(objects)

		counter_data['counter_logic'] = counter_logic

		self.generic_counter()

	def all_users(self, what):
		counter_data = self.counter_data
		counter_data['cls'] = stores.UserData
		counter_data['counter_name'] = 'TotalUsers'
		counter_data['flash_msg'] = 'All Users Counted'

		def counter_logic(objects):
			"""Incriment the counter using the list of objects retrieved"""
			objects = [obj for obj in objects if obj.nickname]
			count = len(objects)
			c = counter.Counter(counter_data['counter_name'],
								counter_data['counter_shards'])
			c.increment(count)
			return count

		counter_data['counter_logic'] = counter_logic
		self.generic_counter()

	def all_profiles(self, what):
		counter_data = self.counter_data
		counter_data['cls'] = stores.Profile
		counter_data['counter_name'] = 'TotalProfiles'
		counter_data['flash_msg'] = 'All Profiles Counted'
		self.generic_counter()

	def all_worlds(self, what):
		counter_data = self.counter_data
		counter_data['cls'] = stores.World
		counter_data['counter_name'] = 'TotalWorlds'
		counter_data['flash_msg'] = 'All Worlds Counted'
		self.generic_counter()

	def user_profiles(self, who):
		author = UserData.load_from_nickname(who)
		counter_data = self.counter_data

		counter_data['cls'] = stores.Profile
		counter_data['counter_name'] = '%sProfiles' % author.key_name
		counter_data['counter_shards'] = 1
		counter_data['flash_msg'] = "%s's Profiles Counted" % author.nickname

		def init_logic():
			"""Return a seed object to use a key from."""
			return stores.Profile.gql(
				'WHERE author = :1 ORDER BY __key__', author).get()

		def query_logic(last_key):
			"""Return a query."""
			return stores.Profile.gql(
				'WHERE author = :1 AND __key__ >= :2 ORDER BY __key__',
				author, last_key
			)

		counter_data['init_logic'] = init_logic
		counter_data['query_logic'] = query_logic
		self.generic_counter()

	def user_worlds(self, who):
		author = UserData.load_from_nickname(who)
		counter_data = self.counter_data

		counter_data['cls'] = stores.World
		counter_data['counter_name'] = '%sWorlds' % author.key_name
		counter_data['counter_shards'] = 1
		counter_data['flash_msg'] = "%s's Worlds Counted" % author.nickname

		def init_logic():
			"""Return a seed object to use a key from."""
			return stores.World.gql(
				'WHERE author = :1 ORDER BY __key__', author).get()

		def query_logic(last_key):
			"""Return a query."""
			return stores.World.gql(
				'WHERE author = :1 AND __key__ >= :2 ORDER BY __key__',
				author, last_key
			)

		counter_data['init_logic'] = init_logic
		counter_data['query_logic'] = query_logic
		self.generic_counter()

	def user_words(self, who):
		author = UserData.load_from_nickname(who)
		counter_data = self.counter_data

		counter_data['cls'] = stores.Profile
		counter_data['counter_name'] = '%sTotalWords' % author.key_name
		counter_data['counter_shards'] = 1
		counter_data['flash_msg'] = "%s's Total Words Counted" % author.nickname

		def init_logic():
			"""Return a seed object to use a key from."""
			return stores.Profile.gql(
				'WHERE author = :1 ORDER BY __key__', author).get()

		def query_logic(last_key):
			"""Return a query."""
			return stores.Profile.gql(
				'WHERE author = :1 AND __key__ >= :2 ORDER BY __key__',
				author, last_key
			)

		def counter_logic(objects):
			"""Incriment the counter using the list of objects retrieved"""
			import operator
			count = reduce(
				operator.add, [obj.word_count or 0 for obj in objects], 0)
			c = counter.Counter(counter_data['counter_name'],
								counter_data['counter_shards'])
			c.increment(count)
			return count

		counter_data['init_logic'] = init_logic
		counter_data['query_logic'] = query_logic
		counter_data['counter_logic'] = counter_logic
		self.generic_counter()

	def world_profiles(self, who):
		world = World.get(who)
		counter_data = self.counter_data

		cls = stores.WorldConnection
		counter_data['cls'] = cls
		counter_data['counter_name'] = '%sWorldProfiles' % world.key_name
		counter_data['counter_shards'] = 1
		counter_data['flash_msg'] = "%s's Profiles Counted" % world.name

		def init_logic():
			"""Return a seed object to use a key from."""
			return cls.gql(
				'WHERE world = :1 ORDER BY __key__', world).get()

		def query_logic(last_key):
			"""Return a query."""
			return cls.gql(
				'WHERE world = :1 AND __key__ >= :2 ORDER BY __key__',
				world, last_key
			)

		counter_data['init_logic'] = init_logic
		counter_data['query_logic'] = query_logic
		self.generic_counter()

	def world_members(self, who):
		world = World.get(who)
		counter_data = self.counter_data

		cls = stores.WorldMember
		counter_data['cls'] = cls
		counter_data['counter_name'] = '%sWorldMembers' % world.key_name
		counter_data['counter_shards'] = 1
		counter_data['flash_msg'] = "%s's Members Counted" % world.name

		def init_logic():
			"""Return a seed object to use a key from."""
			return cls.gql(
				'WHERE world = :1 ORDER BY __key__', world).get()

		def query_logic(last_key):
			"""Return a query."""
			return cls.gql(
				'WHERE world = :1 AND __key__ >= :2 ORDER BY __key__',
				world, last_key
			)

		counter_data['init_logic'] = init_logic
		counter_data['query_logic'] = query_logic
		self.generic_counter()
		self.generic_counter()


	def profile_words(self, who):
		def txn():
			profile = stores.Profile.get(who)
			profile.word_count = utils.word_count(
				profile.apperence, profile.background, profile.extra_info
			)
			profile.put()
			return profile

		profile = db.run_in_transaction(txn)
		self.flash.msg = 'Profile Word Count (%d)' % profile.word_count
		self.redirect(self.request.headers['REFERER'])

# Map URLs to our RequestHandler classes above
_URLS = [
	('^/update/count/([^/]+)/(?:([^/]+)/)?', Count),
	('^/update/([^/]+)/', Index),
]

def main():
	if not random.randint(0, 25):
		framework.profile_main(_URLS)
	else:
		framework.real_main(_URLS)

if __name__ == '__main__':
	main()
