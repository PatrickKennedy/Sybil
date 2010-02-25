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
import	pprint
import	random
import	string
import	sys
import	traceback
import	urllib
import	urlparse

from	urllib	import quote_plus

from	google.appengine.api	import datastore
from	google.appengine.api	import users
from	google.appengine.ext	import webapp

from	common			import framework, utils
from	common.stores	import Profile, World

class Index(framework.BaseRequestHandler):
	def get(self):
		query = Profile.all()
		query.filter('public =', True)
		query.order('-created')
		recent_profiles = query.fetch(5)

		query = World.all()
		query.filter('public =', True)
		query.order('-created')
		recent_worlds = query.fetch(5)

		self.render(['index', 'indexdiscover'], locals())

class DiscoverProfile(framework.BaseRequestHandler):
	def get(self):
		user = utils.get_current_user()
		sort = self.request.get('sort', 'time')
		page = self.request.get_range('page', min_value=1, default=1)
		items_per_page = self.request.get_range('items', min_value=1,
												max_value=25, default=10)
		offset = ((page - 1) * items_per_page)
		last_page = True

		link_template = '<a href="%s">%s</a>'
		sort_links = []
		sort_links.append(link_template % (self.filter_args(['sort', 'page'], sort='time'), 'Time'))
		sort_links.append(link_template % (self.filter_args(['sort', 'page'], sort='words'), 'Word Count'))
		for letter in string.ascii_uppercase:
			sort_links.append(link_template % (self.filter_args(['sort', 'page'], sort=letter.lower()), letter))

		profiles = []
		query = Profile.all()
		query.filter('public =', True)
		if sort == 'time':
			query.order('-created')
		elif sort == 'words':
			query.order('-word_count')
		else:
			query.filter('unix_name >', sort)
			query.filter('unix_name <', sort+u"\ufffd")

		profiles = query.fetch((items_per_page + 1), offset)
		if len(profiles) > items_per_page:
			last_page = False
			profiles.pop()

		self.render(['discover', 'discoverprofile'], locals())

class ProfileFeed(framework.BaseRequestHandler):
	def get(self, output='rss'):
		user 		= utils.get_current_user()
		get 		= self.request.get
		refresh_cache = get('refresh_cache', False) is not False
		sterile_url	= framework.sterilize_url(self.url)

		context = {}

		@framework.memoize(sterile_url, 'profile_feed', refresh=refresh_cache)
		def __fetch_feed_data():
			# Orders the profiles most recently created first.
			q = Profile.all()
			q.filter('public =', True)
			q.order('-created')

			return q.fetch(12)

		context['profile_data'] = {'profiles': __fetch_feed_data()}

		self.render(['feed', 'latestprofiles'], context, output)
		return


class DiscoverWorld(framework.BaseRequestHandler):
	def get(self):
		user = utils.get_current_user()
		sort = self.request.get('sort', 'Time')
		page = self.request.get_range('page', min_value=1, default=1)
		items_per_page = self.request.get_range('items', min_value=1,
												max_value=25, default=10)
		offset = ((page - 1) * items_per_page)
		last_page = True

		link_template = '<a href="%s">%s</a>'
		sort_links = [link_template % (self.filter_args(['sort', 'page'], sort='Time'), 'Time')]
		for letter in string.ascii_uppercase:
			sort_links.append(link_template % (self.filter_args(['sort', 'page'], sort=letter), letter))

		world_list = []
		query = World.all()
		query.filter('public =', True)
		if sort == 'Time':
			query.order('-created')
		else:
			query.filter('name >', sort)
			query.filter('name <', sort+'\x77\x78\x79')

		world_list = query.fetch((items_per_page + 1), offset)
		if len(world_list) > items_per_page:
			last_page = False
			world_list.pop()

		self.render(['discover', 'discoverworld'], locals())

class WorldFeed(framework.BaseRequestHandler):
	def get(self, output='rss'):
		user 		= utils.get_current_user()
		get 		= self.request.get
		refresh_cache = get('refresh_cache', False) is not False
		sterile_url	= framework.sterilize_url(self.url)

		@framework.memoize(sterile_url, 'world_feed', refresh=refresh_cache)
		def __fetch_feed_data():
			# Orders the profiles most recently created first.
			q = World.all()
			q.filter('public =', True)
			q.order('-created')

			return q.fetch(12)

		self.context['world_data'] = {'worlds': __fetch_feed_data()}

		self.render(['feed', 'latestworlds'], output=output)
		return


_URLS = [
	('^/discover/profiles/?', DiscoverProfile),
	('^/discover/profiles/rss/?', ProfileFeed),
	('^/discover/worlds/?', DiscoverWorld),
	('^/discover/worlds/rss/?', WorldFeed),
	('^/discover/?', Index),
]

def main():
	if not random.randint(0, 25):
		framework.profile_main(_URLS)
	else:
		framework.real_main(_URLS)

if __name__ == '__main__':
	main()
