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
import	sys
import	traceback
import	urllib
import	urlparse

from	urllib	import quote_plus

from	google.appengine.api		import datastore
from	google.appengine.api		import users
from	google.appengine.ext		import db, webapp
from	google.appengine.ext.db		import Query

from	common			import const, counter, framework, stores, utils
from	common.stores	import Profile, World, WorldConnection, WorldMember
from	common.stores	import Comment, UserData

class Index(framework.BaseRequestHandler):

	def get(self, name):
		get	= self.request.get
		action = get('action', '')
		if name is None:
			name = get('name', '')
		unix_name = utils.unix_string(name)
		refresh_cache = get("refresh_cache", False) is not False

		if not name:
			self.error(400)
			return

		world = stores.World.get_by_key_name('w:%s' % unix_name)

		if not world or not world.user_can_view(self.udata):
			self.flash.msg = "Unknown World"
			self.redirect('/')
			return

		context = self.context
		context['world'] = world
		context['page_admin'] = utils.page_admin(world.author.user)
		context['page_owner'] = world.author

		if action:
			if action == 'edit':
				self.render(['edit', 'editWorld'])
			elif action == 'delete':
				self.render(['delete', 'deleteWorld'])
			return

		sterile_url = framework.sterilize_url(self.url)

		def __build_profile_data():
			page = self.request.get_range('profiles_page', min_value=1, default=1)
			# Allow page numbers to be more natural
			items_per_page = self.request.get_range('profiles_items', min_value=1,
													max_value=25, default=6)
			offset = ((page - 1) * items_per_page)
			last_page = True

			connections = world.worldconnection_set.fetch(
				(items_per_page + 1), offset
			)
			# This bit of hackery is used to fetch the actual profile objects
			# as opposed to the connection, which don't fetch their references
			# when called inside the html.
			profiles = [conn.profile for conn in connections]
			if len(profiles) > items_per_page:
					last_page = False
					profiles.pop()
					
			@framework.memoize(sterile_url, 'profile_listing', refresh=refresh_cache)
			def fetch():
				return profiles

			return {'profiles': fetch(), 'page':page, 'last_page': last_page}

		@framework.memoize(sterile_url, 'member_listing', refresh=refresh_cache)
		def __fetch_member_data():
			return world.worldmember_set.fetch(25)

		def __build_comment_data():
			page = self.request.get_range('comments_page', min_value=1, default=1)
			# Allow page numbers to be more natural
			items_per_page = self.request.get_range('comments_items', min_value=1,
													max_value=25, default=6)
			offset = ((page - 1) * items_per_page)
			last_page = True

			key = world.key()
			q = Comment.all()
			q.filter('host =', key)
			q.order('-created')
			comments = q.fetch((items_per_page + 1), offset)
			if len(comments) > items_per_page:
				last_page = False
				comments.pop()
				
			@framework.memoize(sterile_url, 'comment_listing', refresh=refresh_cache)	
			def fetch():
				return comments

			return {'comments': comments, 'host': key,
					'page': page, 'last_page': last_page}

		context['profile_data'] = __build_profile_data()
		context['profile_data']['list_author'] = True
		context['profile_data']['list_remove'] = True
		context['profile_data']['list_pages'] = True

		context['member_data'] = {'members': __fetch_member_data()}

		context['comment_data'] = __build_comment_data()
		context['comment_data']['host_type'] = 'world'


		c = counter.Counter('%sWorldProfiles' % world.key_name)
		context['profile_count'] = c.get_count(refresh_cache)
		c = counter.Counter('%sWorldMembers' % world.key_name)
		context['member_count'] = c.get_count(refresh_cache)

		self.render(['view', 'viewWorld'], locals())

class Edit(framework.BaseRequestHandler):

	def get(self, action):
		get = self.request.get
		key_name = get('key_name')
		world = World.get_by_key_name(key_name)

		if not world:
			self.flash.msg = "Unknown World"
			self.redirect('/')
			return

		if get("submit_action", "") == "Cancel":
			self.flash.msg = "%s: Changes Not Saved" % world.name
			self.redirect(world.url)
			return

		if not utils.page_admin(world.author.user) and action != "dismiss_members":
			self.flash.msg = "Access Denied"
			self.redirect(world.url)
			return

		if action == 'add_members':
			members = self.request.get('members', '').split(' ')
			for member in members:
				if member:
					result = self.add_member(world, member)
					if result ==  "Unknown User":
						self.flash.msg = "Unknown User: %s" % member
						self.redirect(world.url)
						return

			self.flash.msg = "User: %s added to World: %s" % (', '.join(members), world.name)
			self.redirect(world.url)
			return

		elif action == 'dismiss_members':
			removed = []
			members = self.request.get('members', '').split(' ')
			for member in members:
				if member:
					result = self.remove_member(world, member)
					if result is True:
						removed.append(member)
					# Silly Easter Egg message to Amanda
					elif result == 'Amanda':
						logging.info('Amanda Message')
						self.flash.msg = "You just can\\\'t get rid of me, Amanda &lt;3"
						self.redirect(world.url)
						return

			self.flash.msg = "User: %s removed from World: %s" % (', '.join(removed), world.name)
			self.redirect(world.url)
			return

		get = self.request.get
		world.about = get('about', '')
		world.links = get('links', '')
		world.common = get('common', '')
		world.open	= get('open', 'True') == 'True'
		world.public = get('public', 'True') == 'True'
		world.markup = get('markup', 'Textile')
		world.put()

		self.flash.msg = "World: %s Saved" % world.name
		self.redirect(world.url)

	# Allow requests to be handled with post or get.
	# This means you can manipulate the world without using a <form>.
	post = get

	def add_member(self, world, username):
		"""remove_member(username: *) -> bool

		Add `username` to the world and return True if wasn't a member already.

		"""

		if not utils.page_admin(world.author.user):
			return False

		udata = stores.UserData.load_from_nickname(username)
		if udata is None:
			return "Unknown User"

		key_name = stores.WorldMember.key_name_form % (world.key_name, udata.key_name)
		member = stores.WorldMember.get_by_key_name(key_name)
		if not member:
			member = WorldMember(key_name=key_name, user=udata, world=world)
			member.put()
			counter.Counter('%sWorldMembers' % world.key_name, 1).increment()

			messages = stores.MessageFactory.gen_user_joined_world(
				world.worldmember_set, member, self.udata
			)
			db.put(messages)

			logging.info('User (%s) has added World (%s) Member (%s)' % (
				self.user.email(), world.name, udata.user.email()))

			framework.unmemoize('/manage/', 'world_listing', udata.nickname)
			framework.unmemoize(member.user.url, 'world_listing')
			framework.unmemoize(world.url, 'member_listing')
			return True

		return False

	def remove_member(self, world, username):
		"""remove_member(username: *) -> bool

		Remove `username` from the world and return True if it was a member.

		"""
		udata = UserData.load_from_nickname(username)
		if udata is None:
			return False

		# Silly Easter Egg message to Amanda
		if False and username == "Pakattack161" and self.udata.nickname == 'WillowCall':
			return 'Amanda'

		if not utils.page_admin(world.author.user) and not utils.page_admin(udata.user):
			return False

		member = world.worldmember_set.filter('user =', udata).get()
		if member:
			for conn in world.worldconnection_set.filter('user = ', udata):
				framework.unmemoize(conn.profile.url, 'world_listing')
				conn.delete()

			logging.info('User (%s) has removed World (%s) Member (%s)' % (
				self.user.email(), world.name, udata.user.email()
				))
			messages = stores.MessageFactory.gen_user_left_world(
				member.world.worldmember_set, member, self.udata
			)
			db.put(messages)

			framework.unmemoize(world.url, 'profile_listing')
			framework.unmemoize('/manage/', 'world_listing', member.user.nickname)
			framework.unmemoize(member.user.url, 'member_listing')
			framework.unmemoize(world.url, 'member_listing')
			member.delete()
			counter.Counter('%sWorldMembers' % world.key_name, 1).increment(-1)
			return True

		return False

class Delete(framework.BaseRequestHandler):

	def post(self):
		get			= self.request.get
		action 		= get('action', 'Cancel')
		name_check	= get('name_check')
		world 		= stores.World.get_by_key_name(get('key_name'))

		if not world:
			self.flash.msg = "Unknown World"
			self.redirect('/')
			return

		if not utils.page_admin(world.author.user):
			self.flash.msg = "Access Denied"
			self.redirect(world.get_absoluete_url())
			return

		if name_check != world.name or action != 'Confirm':
			self.flash.msg = "World: %s Preserved" % world.name
			self.redirect(world.url)
			return

		for connection in world.worldconnection_set:
			framework.unmemoize(connection.profile.url, 'world_listing')
		db.delete(world.worldconnection_set)
		counter.Counter('%sWorldProfiles' % world.key_name, 1).delete()

		for member in world.worldmember_set:
			framework.unmemoize('/manage/', 'world_listing', member.user.nickname)
			framework.unmemoize(member.user.url, 'world_listing')
		db.delete(world.worldmember_set)
		counter.Counter('%sWorldMembers' % world.key_name, 1).delete()

		world.delete()

		c = counter.Counter('TotalWorlds')
		c.increment(-1)

		logging.info('User (%s) deleted World (%s) owned by %s' % (
			self.user.email(), world.name, world.author.user.email()
		))

		framework.unmemoize('/', 'world_listing')
		framework.unmemoize('/discover/', 'world_listing')

		self.flash.msg = "World: %s Deleted" % world.name
		self.redirect('/')

class Join(framework.BaseRequestHandler):

	def post(self):
		user		= utils.get_current_user()
		name		= self.request.get('name', '')
		unix_name	= utils.unix_string(name)
		profile		= Profile.get(self.request.get('profile_key'))
		world		= stores.World.get_by_key_name('w:%s' % unix_name)

		if not name or not profile or not world:
			self.flash.msg = "Unknown World: %s" % name
			self.redirect(self.request.headers['REFERER'])
			return

		page_admin = utils.page_admin(profile.author.user)
		if not page_admin or not world.user_can_post(self.udata):
			self.flash.msg = "Access Denied"
			self.redirect(profile.url)
			return

		connections = profile.worldconnection_set.fetch(6)
		if len(connections) >= 6:
			self.flash.msg = "Profile: %s in too many worlds (Max = 5)" % profile.name
			self.redirect(profile.url)
			return

		if not self.add_profile(world, profile):
			self.flash.msg = "Profile: %s already in World: %s" % (profile.name, world.name)
		else:
			self.flash.msg = "Profile: %s joined World: %s" % (profile.name, world.name)

		self.redirect(profile.url)

	def add_profile(self, world, profile):
		key_name = stores.WorldConnection.key_name_form % (world.key_name, profile.key_name)
		connection = stores.WorldConnection.get_by_key_name(key_name)
		if not connection:
			logging.info('User (%s) has added Profile (%s) to World (%s) ' %
						 (self.user.email(), profile.name, world.name))
			connection = WorldConnection(
							key_name=key_name,
							profile=profile,
							world=world,
						)
			connection.put()
			counter.Counter('%sWorldProfiles' % world.key_name, 1).increment()

			messages = stores.MessageFactory.gen_profile_joined_world(
				world.worldmember_set, connection, self.udata
			)

			db.put(messages)

			framework.unmemoize(profile.url, 'world_listing')
			framework.unmemoize(world.url, 'profile_listing')
			return True

		return False

class Leave(framework.BaseRequestHandler):

	def get(self):
		logging.info('PROFILE KEY: %r' % self.request.get('profile_key'))
		profile		= Profile.get_by_key_name(self.request.get('profile_key'))
		world 		= World.get_by_key_name(self.request.get('world_key'))

		if not profile:
			self.flash.msg = "Error: Unable to load profile"
			self.redirect('/')
			return

		if not world:
			self.flash.msg = "Error: Unable to load World"
			self.redirect('/')
			return

		page_admin = utils.page_admin(profile.author.user)
		if not page_admin:
			self.flash.msg = "Access Denied"
			self.redirect(self.request.headers['REFERER'])
			return

		self.remove_profile(world, profile)

		self.flash.msg = "Profile: %s removed from World: %s" % (profile.name, world.name)
		self.redirect(profile.url)

	def remove_profile(self, world, profile):
		key_name = stores.WorldConnection.key_name_form % (world.key_name, profile.key_name)
		connection = stores.WorldConnection.get_by_key_name(key_name)

		if connection:
			connection.delete()
			counter.Counter('%sWorldProfiles' % world.key_name, 1).increment(-1)

			logging.info('User (%s) has removed Profile (%s) from World (%s)' %
						 (self.user.email(), world.name, profile.author.user.email()))

			messages = stores.MessageFactory.gen_profile_left_world(
				world.worldmember_set, connection, self.udata
			)
			db.put(messages)

			framework.unmemoize(profile.url, 'world_listing')
			framework.unmemoize(world.url, 'profile_listing')
			return True

		return False


# Map URLs to our RequestHandler classes above
_URLS = [
  #('^/world/([^/]*)/?', ViewWorld),
  ('^/world/?', Index),
  ('^/world/edit/([^/]*)/?', Edit),
  ('^/world/delete/?', Delete),
  ('^/world/join/?', Join),
  ('^/world/leave/?', Leave),
]

def main():
	if not random.randint(0, 25):
		framework.profile_main(_URLS)
	else:
		framework.real_main(_URLS)

if __name__ == '__main__':
	main()
