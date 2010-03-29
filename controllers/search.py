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

import	logging

from common import const, counter, framework, memopad, stores
from lib.search import SEARCH_PHRASE_MIN_LENGTH

class Index(framework.BaseRequestHandler):
	def get(self):
		search_phrase = self.request.get('q')
		too_short = False
		if len(search_phrase) < SEARCH_PHRASE_MIN_LENGTH:
			too_short = True
			self.flash.msg = "Search Query is too short. Minimum length is %s" % SEARCH_PHRASE_MIN_LENGTH
		refresh_cache = self.request.get('refresh_cache', False) is not False
		sterile_url = memopad.sterilize_url(self.url)

		@memopad.paginate(self, 'profiles')
		@memopad.learn(sterile_url, 'profiles_listing', search_phrase, skip=refresh_cache)
		def _paginate_profile_data(limit, offset, bookmark):
			return stores.Profile.search(
				search_phrase, limit=limit, bookmark=bookmark, offset=offset)

		@memopad.paginate(self, 'worlds')
		@memopad.learn(sterile_url, 'worlds_listing', search_phrase, skip=refresh_cache)
		def _paginate_world_data(limit, offset, bookmark):
			return stores.World.search(
				search_phrase, limit=limit, bookmark=bookmark, offset=offset)

		# Perform the length check outside the function so we're not hitting
		# the memopad at all.
		profile_data = {}
		if not too_short:
			profile_data = _paginate_profile_data()

		self.context['profile_data'] = profile_data
		self.context['profile_data']['list_author'] = True
		self.context['profile_data']['list_pages'] = True

		world_data = {}
		if not too_short:
			world_data = _paginate_world_data()

		self.context['world_data'] = world_data
		self.context['world_data']['list_pages'] = True

		self.render(['index', 'search'])
		return
