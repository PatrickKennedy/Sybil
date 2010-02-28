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

from __future__ import with_statement

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


from	common			import counter, stores, framework, memopad, utils
from	common.stores	import UserData
from	common.stores	import Profile, World, Comment, WorldMember

class Index(framework.BaseRequestHandler):

	def get(self):
		len_ 		= self.request.get_range('length', min_value=3,
											 max_value=10, default=6)
		names 		= self.get_name_list(5, len_)
		get			= self.request.get
		refresh_cache = get('refresh_cache', False) is not False

		if get('logit', False) is not False:
			from google.appengine.api.labs	import taskqueue
			taskqueue.add(url='/tasks/logging/')

		context = self.context
		context['len_'] = len_
		context['names'] = names

		sterile_url = memopad.sterilize_url(self.request.url)

		#@memopad.learn(sterile_url, 'profile_listing', version_key='profile_listing', skip=refresh_cache)
		@memopad.learn(sterile_url, 'profile_listing', skip=refresh_cache)
		def __fetch_profile_data():
			query = stores.Profile.all()
			query.filter('public =', True)
			query.order('-updated')
			return query.fetch(5)

		#@memopad.learn(sterile_url, 'world_listing', version_key='world_listing', skip=refresh_cache)
		@memopad.learn(sterile_url, 'world_listing', skip=refresh_cache)
		def __fetch_world_data():
			query = World.all()
			query.filter('public =', True)
			query.order('-created')
			return query.fetch(5)

		context['profile_data'] = {
			'profiles': __fetch_profile_data(),
			'list_author': True
		}

		context['world_data'] = {
			'worlds': __fetch_world_data(),
			'list_author': True,
		}

		profile_count = counter.Counter('TotalProfiles').get_count(refresh_cache)
		world_count = counter.Counter('TotalWorlds').get_count(refresh_cache)
		user_count = counter.Counter('TotalUsers').get_count(refresh_cache)
		context['profile_count'] = profile_count
		context['world_count'] = world_count
		context['user_count'] = user_count

		self.render(['index', 'index'])

	def post(self):
		self.redirect('/' + self.args_to_url())

class PrintEnviron(webapp.RequestHandler):
  def get(self):
    for name in os.environ.keys():
      self.response.out.write("<b>%s</b> = %s<br />\n" % (name, os.environ[name]))

class ChangeLog(framework.BaseRequestHandler):
	def get(self):
		self.render(['index', 'changelog'])

class EditProfile(framework.BaseRequestHandler):

	def get(self, username, name):
		adata	= UserData.load_from_nickname(username)
		author		= adata.user
		page_admin 	= self.page_admin(author)

		name		= urllib.unquote_plus(urllib.unquote(name))
		unix_name 	= utils.unix_string(name)

		context = self.context
		context['author'] = author
		context['page_author'] = adata
		context['page_admin'] = page_admin

		# Check to see if we already have a profile for that character.
		# profile = Profile.gql('WHERE unix_name = :name AND author = :author',
		#					  name=unix_name, author=adata).get()
		profile = Profile.get_by_key_name(
			stores.Profile.key_name_form % (unix_name, adata.key_name)
		)

		# If we can't find that character and we're the author we may want to
		# make it, other wise we should move the user back to the user page.
		if not profile or (not profile.public and not page_admin):
			self.flash.msg = "Unknown Profile: %s" % name
			if author == self.user:
				self.redirect('/create/profile/?name=%s' % name)
			else:
				self.redirect(adata.url)
			return

		context['profile'] = profile

		self.render(['edit', 'editprofile'])

	def post(self, username, name):
		adata	= UserData.load_from_nickname(username)
		author		= adata.user

		get		= self.request.get
		public 	= get('public', 'True') == 'True'
		markup	= get('markup', 'Textile')
		key_name = get('key_name')

		profile = stores.Profile.get_by_key_name(key_name)

		if not profile:
			self.redirect('/create/profile/%s' % self.args_to_url())
			return

		if get("submit_action", "Cancel") == "Cancel":
			self.flash.msg = '%s: Not Updated' % profile.name
			self.redirect(profile.url)
			return

		# Only let admins and the author edit a profile
		if not self.page_admin(author):
			self.flash.msg = "Access Denied."
			self.redirect(profile.url)
			return

		changed = []
		def txn():
			new_args = self.args_to_dict()
			new_args.update({
				'public':public,'markup':markup,
				'updated':datetime.datetime.now()
			})
			if 'name' in new_args:
				del new_args['name'] # Make it impossible to change the name.

			for arg in profile.properties():
				if arg not in new_args:
					continue
				new_arg = new_args.get(arg)
				if new_arg == getattr(profile, arg):
					continue
				changed.append(arg)
				setattr(profile, arg, new_arg)
			profile.word_count = utils.word_count(
				profile.apperence, profile.background, profile.extra_info
			)
			profile.put()
		db.run_in_transaction(txn)
		logging.info("User (%s) has made changes (%s) to a Profile (%s)" %
					 (self.user.email(), ' | '.join(changed), profile.name))

		# Clear the profile from the memcache.
		#Profile.unload(adata.key_name, profile.unix_name)
		#TODO: Transition from memopad.forget's to versioning
		# Update the global cache
		#memcache.incr('profile_listing', 1, 'cache_version', 0)
		# Update the latest profiles list on the front page.
		memopad.forget('/', 'profile_listing')

		self.flash.msg = "%s: Updated" % profile.name

		self.redirect(profile.url)


class DeleteProfile(framework.BaseRequestHandler):

	def get(self, username, name):
		adata	= UserData.load_from_nickname(username)
		author		= adata.user
		page_admin 	= self.page_admin(author)

		name		= urllib.unquote_plus(urllib.unquote(name))
		unix_name 	= utils.unix_string(name)

		context = self.context
		context['author'] = author
		context['page_author'] = adata
		context['page_admin'] = page_admin

		# Check to see if we already have a profile for that character.
		profile = Profile.get_by_key_name(
			stores.Profile.key_name_form % (unix_name, adata.key_name)
		)

		# If we can't find that character and we're the author we may want to
		# make it, other wise we should move the user back to the user page.
		if not profile or (not profile.public and not page_admin):
			self.flash.msg = "Unknown Profile: %s" % name
			self.redirect(Profile.get_url(username))
			return

		context['profile'] = profile

		self.render(['delete', 'deleteprofile'], context)

	def post(self, username, name):
		adata	= UserData.load_from_nickname(username)
		author		= adata.user

		choice	= self.request.get('choice')
		name_check	= self.request.get('name_check')
		profile_key = self.request.get('profile_key', '')

		profile = Profile.get(profile_key)

		if not profile:
			self.flash.msg = "Unknown Profile"
			self.redirect(adata.url)
			return

		# Only let admins and the author delete a profile
		if not self.page_admin(self.user):
			self.flash.msg = "Access Denied."
			self.redirect(profile.url)
			return

		if name_check != profile.name or choice != 'Confirm':
			self.flash.msg = "%s: Preserved" % profile.name
			self.redirect(profile.url)
			return

		query = Comment.all()
		query.filter('host =', profile)
		for comment in query:
			comment.delete()
		for conn in profile.worldconnection_set:
			conn.delete()
		# Clear the profile from the memcache.
		#Profile.unload(adata.key_name, profile.unix_name)
		profile.delete()

		c = counter.Counter('TotalProfiles')
		c.increment(-1)
		c = counter.Counter('%sProfiles' % profile.author.key_name, 1)
		c.increment(-1)

		logging.info("%s(%s) deleted %s's Profile (%s)." % (
					 self.user.email(), self.udata.nickname,
					 profile.author.user.email(), profile.name
		))

		#TODO: Transition from memopad.forget's to versioning
		# Update the global cache
		#memcache.incr('profile_listing', 1, 'cache_version', 0)
		# Update the profile author's cache
		#memcache.incr(profile.author.key_name +'_profile_listing', 1, 'cache_version', 0)

		memopad.forget('/manage/', 'profile_listing', adata.nickname)
		memopad.forget('/', 'profile_listing')
		memopad.forget('/discover/', 'profile_listing')
		memopad.forget('/discover/', 'profile_feed')
		memopad.forget(profile.author.url, 'profile_listing')
		memopad.forget(profile.author.url, 'profile_feed')

		self.flash.msg = "%s Deleted Sucessfully" % profile.name
		self.redirect(profile.author.url)

class ViewProfile(framework.BaseRequestHandler):

	def get(self, username, name):
		adata = UserData.load_from_nickname(username)
		author	= adata.user
		get 	= self.request.get
		if name is None:
			name 	= get('name', '')
		output		= get('output', '')

		# If we're loading the user's public page and not a profile
		if not name:
			if output in ["rss", "atom"]:
				self.render_feed(user, author, adata, output)
			else:
				self.render_user(user, author, adata)
			return

		name = urllib.unquote_plus(urllib.unquote(name))
		unix_name 	= utils.unix_string(name)

		page_admin 	= self.page_admin(author)
		action 		= get('action')
		refresh_cache = get('refresh_cache', False) is not False
		index = get('index', False) is not False
		sterile_url	= memopad.sterilize_url(self.url)

		context = self.context
		context['author'] = author
		context['page_author'] = adata
		context['page_admin'] = page_admin

		# Check to see if we already have a profile for that character.
		# profile = Profile.gql('WHERE unix_name = :name AND author = :author',
		#					  name=unix_name, author=adata).get()
		profile = stores.Profile.get_by_key_name(
			stores.Profile.key_name_form % (unix_name, adata.key_name)
		)

		# If we can't find that character and we're the author we may want to
		# make it, other wise we should move the user back to the user page.
		if not profile or (not profile.public and not page_admin):
			self.flash.msg = "Unknown Profile: %s" % name
			if author == self.user:
				self.redirect('/create/profile/name=%s' % name)
			else:
				self.redirect(adata.url)
			return

		if index:
			profile.index()

		# Check for actions
		if action:
			if action == 'edit':
				self.render(['edit', 'editprofile'], locals())
			elif action == 'delete':
				self.render(['delete', 'deleteprofile'], locals())
			return

		#@memopad.learn(sterile_url, 'world_listing', version_key='world_listing', skip=refresh_cache)
		@memopad.learn(sterile_url, 'world_listing', skip=refresh_cache)
		def __fetch_world_data():
			# This bit of hackery is used to fetch the actual world objects
			# as opposed to the connection, which don't fetch their references
			# when called inside the html.
			return [conn.world for conn in profile.worldconnection_set.fetch(5)]


		def __build_comment_data():
			page = self.request.get_range('comments_page', min_value=1, default=1)
			items_per_page = self.request.get_range(
				'comments_items', min_value=1, max_value=25, default=6
			)
			offset = ((page - 1) * items_per_page)
			last_page = True

			key = profile.key()
			q = Comment.all()
			q.filter('host =', key)
			q.order('-created')
			comments = q.fetch((items_per_page + 1), offset)
			if len(comments) > items_per_page:
				last_page = False
				comments.pop()

			@memopad.learn(sterile_url, 'comment_listing', skip=refresh_cache)
			def fetch():
				return comments

			return {'comments': fetch(), 'host': key, 'host_type': 'profile',
					'page': page, 'last_page': last_page}

		context['world_data'] = {
			'worlds': __fetch_world_data(),
			'list_author': True,
		}

		context['comment_data'] = __build_comment_data()

		if refresh_cache:
			memcache.delete('markup:%s' % profile.key_name)

		self.render(['view', 'viewProfile'], locals())

class ViewUser(framework.BaseRequestHandler):
	def get(self, username):
		get 		= self.request.get
		name 		= get('name')
		if name:
			# Redriect people to the updated url format.
			self.redirect(Profile.get_url(username, urllib.quote_plus(name)),
						  permanent=True)
			return

		adata	= UserData.load_from_nickname(username)
		if not adata:
			self.redirect('/404/')
			return

		author		= adata.user
		page_admin 	= self.page_admin(author)
		get 		= self.request.get
		action 		= get('action')
		refresh_cache = get('refresh_cache', False) is not False
		sterile_url	= memopad.sterilize_url(self.request.url)

		context = self.context
		context['author'] = author
		context['adata'] = adata
		context['page_admin'] = page_admin


		#TODO: Convert this to memopad.paginate
		def __build_profile_data():
			order 	= get('order', 'created').lower()
			page 	= self.request.get_range('profiles_page', min_value=1, default=1)
			# Allow page numbers to be more natural
			items_per_page = self.request.get_range('profiles_items', min_value=1,
											max_value=25, default=10)
			offset = ((page - 1) * items_per_page)
			last_page = True

			# Orders the profiles most recently created first.
			query = Profile.all()
			query.filter('author =', adata)
			if not page_admin:
				query.filter('public =', True)
			if order == 'alpha':
				query.order('name')
			else:
				query.order('-created')
			profiles = query.fetch((items_per_page + 1), offset)

			# Since each page is 6 items long if there are 7 items then we
			# know that there is at least one more page.
			if len(profiles) > items_per_page:
				last_page = False
				profiles.pop()

			#@memopad.learn(sterile_url, 'profile_listing', version_key=adata.key_name +'profile_listing', skip=refresh_cache)
			@memopad.learn(sterile_url, 'profile_listing', skip=refresh_cache)
			def fetch():
				return profiles

			return {'profiles':fetch(), 'page':page, 'last_page':last_page}

		#@memopad.learn(sterile_url, 'world_listing', version_key=adata.key_name +'world_listing', skip=refresh_cache)
		@memopad.learn(sterile_url, 'world_listing', skip=refresh_cache)
		def __fetch_world_memberships():
			query = WorldMember.all()
			query.filter('user =', adata)
			return [membership.world for membership in query.fetch(10)]


		context['profile_data'] = __build_profile_data()
		context['profile_data']['partial_listing'] = True
		context['profile_data']['list_edit'] = True
		context['profile_data']['list_pages'] = True

		context['world_data'] = {
			'worlds': __fetch_world_memberships(),
			'list_author': True,
		}

		c = counter.Counter('%sProfiles' % adata.key_name, 1)
		context['profile_count'] = c.get_count(refresh_cache)

		c = counter.Counter('%sWorlds' % adata.key_name, 1)
		context['world_count'] = c.get_count(refresh_cache)

		c = counter.Counter('%sTotalWords' % adata.key_name, 1)
		context['total_word_count'] = c.get_count(refresh_cache)


		self.render(['view', 'viewUser'])
		return

class UserFeed(framework.BaseRequestHandler):
	def get(self, username, output):
		adata	= UserData.load_from_nickname(username)
		author		= adata.user
		page_admin 	= self.page_admin(author)
		get 		= self.request.get
		refresh_cache = get('refresh_cache', False) is not False
		sterile_url	= memopad.sterilize_url(self.request.url)

		self.context['author'] = author
		self.context['adata'] = adata
		self.context['page_admin'] = page_admin

		#@memopad.learn(sterile_url, 'profile_feed', version_key=adata.key_name +'profile_listing', skip=refresh_cache)
		@memopad.learn(sterile_url, 'profile_feed', skip=refresh_cache)
		def __fetch_feed_data():
			# Orders the profiles most recently created first.
			q = adata.profile_set
			q.order('-created')

			return q.fetch(12)

		profile_data = {'profiles': __fetch_feed_data()}

		self.render(['feed', 'userprofiles'], output=output)
		return

# Map URLs to our RequestHandler classes above
_URLS = [
	('^/', Index),
	('^/changelog/', ChangeLog),
	('^/env/', PrintEnviron),
	('^/([^/]+)/(rss|atom|feed)/?', UserFeed),
	('^/([^/]+)/([^/]+)/edit/?', EditProfile),
	('^/([^/]+)/([^/]+)/delete/?', DeleteProfile),
	('^/([^/]+)/([^/]+)/?', ViewProfile),
	('^/([^/]+)/?', ViewUser),
]

def main():
	if not random.randint(0, 25):
		framework.profile_main(_URLS)
	else:
		framework.real_main(_URLS)

if __name__ == '__main__':
	main()
