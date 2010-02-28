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
import	traceback
import	urllib
import	urlparse
import	wsgiref.handlers

from	urllib	import quote_plus

from	google.appengine.api		import datastore, memcache
from	google.appengine.ext		import db, webapp

from	common			import const, counter, framework, memopad, utils
from	common.stores	import UserData, Profile, WorldMember, Message

class Index(framework.BaseRequestHandler):
	def get(self):
		delinate	= self.udata.nickname
		refresh_cache = self.request.get('refresh_cache', False) is not False
		sterile_url = memopad.sterilize_url(self.url)

		self.context['page_admin'] = True
		self.context['designs'] = const.AVAILABLE_DESIGNS
		self.context['themes'] = const.AVAILABLE_THEMES
		self.context['cf_scripts'] = const.CF_SCRIPTS

		@memopad.learn(sterile_url, 'profile_listing', delinate, skip=refresh_cache)
		def __fetch_latest_profiles():
			query = Profile.all()
			query.filter('author =', self.udata)
			query.order('-created')
			return query.fetch(5)

		# TODO: Reimplement the messaging system. The new one will be cache compatable.
		@memopad.learn(sterile_url, 'message_listing', delinate, skip=refresh_cache)
		def __fetch_messages():
			q = self.udata.message_recipient_set
			q.order('-created')
			return q.fetch(25)

		@memopad.learn(sterile_url, 'world_listing', delinate, skip=refresh_cache)
		def __fetch_world_memberships():
			q = self.udata.worldmember_set
			#q = WorldMember.all()
			#q.filter('user =', udata)
			return [membership.world for membership in q.fetch(10)]


		self.context['profile_data'] = {
			'profiles': __fetch_latest_profiles(),
			'list_edit': True,
		}

		self.context['messages'] = __fetch_messages()

		self.context['world_data'] = {
			'worlds': __fetch_world_memberships(),
			'list_leave': True,
		}

		self.render(['index', 'indexManage'])

class SearchIndexing(framework.BaseRequestHandler):
	def get(self, type):
		for profile in self.udata.profile_set:
			profile.enqueue_indexing(url='/tasks/index/')
		for world in self.udata.world_set:
			world.enqueue_indexing(url='/tasks/index/')
		self.flash.msg = 'All Profiles and Worlds queued for indexing.'
		self.redirect('/manage/')
		return

class Update(framework.BaseRequestHandler):
	def get(self):

		def txn():
			get		= self.request.get
			design	= get('design')
			theme	= get('theme')
			use_custom_css 	= get('use_custom_css')
			if use_custom_css is not None:
				use_custom_css = use_custom_css == 'on'
			cf_script		= get('cf_script')
			use_custom_cf 	= get('use_custom_cf')
			if use_custom_cf is not None:
				use_custom_cf = use_custom_cf == 'on'
			ga_code 	= get('ga_code')
			nickname	= get('nickname')
			wave_address   = get('wave_address')
			udata		= self.udata
			changes 	= []

			if not udata:
				self.redirect('/')

			if theme is not None and udata.theme != theme:
				changes.append('Theme: %s -> %s' % (udata.theme, theme))
				udata.theme = theme

			if design is not None and udata.design != design:
				changes.append('Design: %s -> %s' % (udata.design, design))
				udata.design = design

			if use_custom_css is not None and udata.use_custom_css != use_custom_css:
				changes.append('Use Custom CSS: %s -> %s' % (not use_custom_css, use_custom_css))
				udata.use_custom_css = use_custom_css

			if cf_script is not None and udata.cf_script != cf_script:
				changes.append('CF Script: %s -> %s' % (udata.cf_script, cf_script))
				udata.cf_script = cf_script

			if use_custom_cf is not None and udata.use_custom_cf != use_custom_cf:
				changes.append('Use Custom CF: %s -> %s' % (not use_custom_cf, use_custom_cf))
				udata.use_custom_cf = use_custom_cf

			if ga_code is not None and udata.ga_code != ga_code:
				changes.append('Google Analytics Code: %s -> %s' % (udata.ga_code, ga_code))
				udata.ga_code = ga_code.strip()

			if nickname is not None and udata.nickname != nickname:
				import re
				nickname = re.sub('[^a-zA-Z0-9\.\-_]*', '', nickname)
				unix_nick = nickname.lower()
				changes.append('Nickname: %s -> %s' % (udata.nickname, nickname))
				memcache.delete("nickpointer:%s" % udata.unix_nick)
				memcache.set("nickpointer:%s" % unix_nick, udata)
				udata.nickname = nickname
				udata.unix_nick = unix_nick

			if wave_address is not None and udata.wave_address != wave_address:
				changes.append('Wave Address: %s -> %s' % (udata.wave_address, wave_address))
				#TODO: Delete wave_address pointers similarly to nickpointers
				#memcache.delete('wavepointer:%s' % udata.wave_address)
				#memcache.set('wavepointer:%s' % wave_address, udata)
				udata.wave_address = wave_address

			if changes:
				udata.put()
				logging.info('%s made %d preference change(s)\n%s' %
							 (udata.user.email(), len(changes), '\n'.join(changes)))

		db.run_in_transaction(txn)
		self.flash.msg = "Changes Saved"
		self.redirect('/manage/')

class UpdateSingle(framework.BaseRequestHandler):
	def get(self, attr):
		unix_attr = attr.lower()
		value = self.request.get("value", None)
		next = self.request.get('next')
		udata = UserData.load()

		if value is None:
			return

		def txn():
			if value != getattr(udata, unix_attr, None):
				logging.info('%s changed %s from %s to %s' %
							 (udata.user.email(), attr, getattr(udata, attr), value))
				setattr(udata, unix_attr, value)
				udata.put()

		db.run_in_transaction(txn)
		self.flash.msg = "Changes Saved"
		self.redirect(next or '/manage/')




class Edit(framework.BaseRequestHandler): pass

class Dismiss(framework.BaseRequestHandler):

	def get(self):
		get		= self.request.get
		type	= get('type').lower()
		key		= get('key')
		if type and key:
			try:
				getattr(self, '_type_%s' % type)(key)
			except AttributeError:
				pass

		self.redirect(self.request.headers.get('REFERER', '/manage/'))

	def _type_message(self, message_key):
		message = Message.get(message_key)
		if not message:
			return

		message.delete()

URLS = [
	('^/manage/?', Index),
	('^/manage/index/([^\/]+)/?', SearchIndexing),
	('^/manage/update/([^\/]+)/?', UpdateSingle),
	('^/manage/update/?', Update),
	('^/manage/edit/?', Edit),
	('^/manage/dismiss/?', Dismiss),
]
