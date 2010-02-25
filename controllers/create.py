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

import datetime
import logging
import os
import pprint
import random
import sys
import traceback
import urllib
import urlparse
import uuid

from urllib	import quote_plus

from google.appengine.api.labs	import taskqueue
from google.appengine.api		import capabilities, datastore, memcache, users
from google.appengine.ext		import db, webapp
from google.appengine.runtime	import apiproxy_errors

from common			import counter, framework, stores, utils


class Index(framework.BaseRequestHandler):
	def get(self):
		len_	= self.request.get_range(
			'length', min_value=3, max_value=10, default=6)
		names	= self.get_name_list(5, len_)

		# Check if datastore writes are possible
		if capabilities.CapabilitySet('datastore_v3', ['write']).is_enabled():
			self.render(['index', 'indexNew'], self.args_to_dict(len_=len_, names=names))
		else:
			if self.request.query_string:
				self.context['return_url'] = self.url
			self.render(['error', 'ReadOnly'])

class NewProfile(framework.BaseRequestHandler):
	def get(self):
		# Check if datastore writes are possible
		if capabilities.CapabilitySet('datastore_v3', ['write']).is_enabled():
			self.render(['new', 'newProfile'], self.args_to_dict())
		else:
			if self.request.query_string:
				self.context['return_url'] = self.url
			self.render(['error', 'ReadOnly'])

	def post(self):
		get		= self.request.get
		name	= get('name', '')
		unix_name = utils.unix_string(name)

		if not name:
			self.flash.msg = "Error: Name Required"
			self.redirect(self.args_to_url())
			return

		key_name = stores.Profile.key_name_form % (unix_name, self.udata.key_name)

		if stores.Profile.get_by_key_name(key_name):
			self.flash.msg = "Error: Profile (%s) Already Exists" % name
			self.render(['new', 'newProfile'], self.args_to_dict())
			return

		now = datetime.datetime.now()

		def txn():
			profile = stores.Profile(
				key_name=key_name,
				created=now,
				updated=now,
				author=self.udata,
				name=name,
				unix_name=unix_name,
			)
			profile.public	= get('public', 'True') == 'True'
			profile.markup	= get('markup', 'Textile')
			profile.age		= get('age', '')
			profile.gender	= get('gender', '')
			profile.race	= get('race', '')
			profile.height	= get('height', '')
			profile.weight	= get('weight', '')
			profile.apperence	= get('apperence', '')
			profile.background	= get('background', '')
			profile.extra_info	= get('extra_info', '')
			profile.links	= get('links', '')
			profile.common	= get('common', '')
			profile.word_count = utils.word_count(
				profile.apperence, profile.background, profile.extra_info
			)
			profile.put()
			return profile

		try:
			profile = db.run_in_transaction(txn)
		except apiproxy_errors.CapabilityDisabledError:
			self.flash.msg = "Error: App Engine could not create your profile."
			self.render(['new', 'newProfile'], self.args_to_dict())
			return
		except (db.Error, apiproxy_errors.Error):
			self.flash.msg = "Error: App Engine could not create your profile for an unknown reason."
			self.render(['new', 'newProfile'], self.args_to_dict())
			return

		c = counter.Counter('TotalProfiles')
		c.increment()
		c = counter.Counter('%sProfiles' % self.udata.key_name, 1)
		c.increment()

		logging.info('User (%s) has made a new character (%s)' %
					 (self.udata.user.email(), profile.name))

		framework.unmemoize('/manage/', 'profile_listing', self.udata.nickname)
		framework.unmemoize('/', 'profile_listing')
		framework.unmemoize('/discover/', 'profile_listing')
		framework.unmemoize('/discover/', 'profile_feed')
		framework.unmemoize(profile.author.url, 'profile_listing')
		framework.unmemoize(profile.author.url, 'profile_feed')

		self.flash.msg = "%s has been created" % name
		self.redirect(profile.url)

class NewComment(framework.BaseRequestHandler):

	def post(self):
		"""Create a new comment and related messages.
		All type functions should return an unput comment."""
		get		= self.request.get
		markup	= get('markup', 'Textile')
		type 	= get('type').lower()
		host 	= get('host')

		func_name = '_type_%s' % type
		if hasattr(self, func_name):
			# Build the comment base with common properties.
			comment = stores.Comment(markup=markup)
			# Pass the comment and the host data for final processing
			getattr(self, func_name)(comment, host)
			# Delete a previous cache entry
			logging.info("REFERER: "+self.request.headers['REFERER'])
			framework.unmemoize(self.request.headers['REFERER'], 'comment_listing')
		else:
			logging.error('User (%s) attempted to create an unknown type of comment (%s)' %
						  (utils.get_current_user(), type))

		self.redirect(self.request.headers['REFERER'])

	def _type_locational(self, comment):
		body = self.request.get('body')
		location = self.request.get('location')
		if body and location:
			comment = LocationalComment(
				owner = stores.UserData.load(users.get_current_user()),
				location = location,
				body = body
			)

			return comment

	def _type_world(self, comment, world_key):
		body = self.request.get('body')
		world = db.get(world_key)
		if body and world:
			comment.author = self.udata
			comment.host = world.key()
			comment.body = body
			comment.put()

			for member in world.worldmember_set:
				stores.Message.from_comment(member.user, comment).put()


	def _type_profile(self, comment, profile_key):
		body = self.request.get('body')
		profile = db.get(profile_key)
		if body and profile:
			comment.author = self.udata
			comment.host = profile.key()
			comment.body = body
			comment.put()

			stores.Message.from_comment(profile.author, comment).put()

class NewWorld(framework.BaseRequestHandler):

	def get(self):
		# Check if datastore writes are possible
		if capabilities.CapabilitySet('datastore_v3', ['write']).is_enabled():
			self.render(['new', 'newWorld'], self.args_to_dict())
		else:
			if self.request.query_string:
				self.context['return_url'] = self.url
			self.render(['error', 'ReadOnly'])

	def post(self):
		name	= self.request.get('name', '')
		unix_name = utils.unix_string(name)

		if not name:
			self.flash.msg = "Error: Name Required"
			self.render(['new', 'newWorld'], self.args_to_dict())
			return

		key_name = 'w:%s' % unix_name
		if stores.World.get_by_key_name(key_name):
			self.flash.msg = "Error: World already exists"
			self.render(['new', 'newWorld'], self.args_to_dict())
			return

		get = self.request.get
		# Due to the nature of the lazy property, using self.udata within the
		# txn may cause the txn to act on two properties (loading the udata).
		adata = self.udata
		def txn():
			now = datetime.datetime.now()
			world = stores.World(
				created=now,
				author=adata,
				name=name,
				unix_name=unix_name,
				key_name=key_name,
			)
			world.about = get('about', '')
			world.links = get('links', '')
			world.public = (get('public', 'True') == 'True')
			world.open = (get('open', 'False') == 'True')
			world.markup = get('markup', 'Textile')
			world.put()
			return world

		try:
			world = db.run_in_transaction(txn)
		except apiproxy_errors.CapabilityDisabledError:
			self.flash.msg = "Error: Sybil could not create your world."
			self.render(['new', 'newWorld'], self.args_to_dict())
			return
		except (db.Error, apiproxy_errors.Error), e:
			logging.error(e)
			self.flash.msg = "Error: Sybil could not create your world for an unknown reason."
			self.render(['new', 'newWorld'], self.args_to_dict())
			return

		key_name = stores.WorldMember.key_name_form % (world.key_name, adata.key_name)
		def txn():
			member = stores.WorldMember(key_name=key_name, user=adata, world=world)
			member.put()
			return member

		try:
			member = db.run_in_transaction(txn)
		except (db.Error, apiproxy_errors.Error):
			self.flash.msg = "Note: Sybil could not add you to your world, but will keep trying."
			taskqueue.add(
				url='/tasks/world/add/member/',
				params={
					'udata':str(udata.key()),
					'world':str(world.key())
				}
			)

		c = counter.Counter('TotalWorlds')
		c.increment()
		c = counter.Counter('%sWorlds' % self.udata.user_id(), 1)
		c.increment()

		logging.info('User (%s) has made a new world (%s)' %
					 (self.user.email(), world.name))

		framework.unmemoize('/', 'world_listing')
		framework.unmemoize('/discover/', 'world_listing')
		framework.unmemoize('/manage/', 'world_listing', self.udata.nickname)

		self.flash.msg = "World (%s) created" % unix_name
		self.redirect(world.url)

_URLS = [
	('^/create/profile/?', NewProfile),
	('^/create/comment/?', NewComment),
	('^/create/world/?', NewWorld),
	('^/create/?', Index),
]

def main():
	if not random.randint(0, 25):
		framework.profile_main(_URLS)
	else:
		framework.real_main(_URLS)

if __name__ == '__main__':
	main()
