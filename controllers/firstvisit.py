#!/usr/bin/env python

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
import random
import re
import sys
import traceback
import urllib
import urlparse

from google.appengine.api import datastore, users
from google.appengine.ext import webapp

from common			import counter, framework, stores, utils

class Index(framework.BaseRequestHandler):
	def get(self):
		user = self.user
		continue_ = self.request.get('continue', '/')

		if self.user:
			if not self.udata or not self.udata.nickname:
				self.redirect('/first/visit/?continue=%s' % continue_)
				return

		self.redirect(continue_)


class FirstVisit(framework.BaseRequestHandler):
	def get(self):
		get		= self.request.get
		continue_	= get('continue', '/')
		taken		= get('taken', False) is not False

		udata = self.udata
		if udata and udata.nickname:
			self.flash.msg = "Error: You've already been here!"
			self.redirect(continue_)
			return

		self.render('firstVisit', locals())

	def post(self):
		get	= self.request.get
		nick = get('nick')
		nick = re.sub('[^a-zA-Z0-9.\-_]*', '', nick)
		unix_nick = nick.lower()
		continue_ = get('continue', '/')

		if not self.user:
			self.error(400)

		udata = stores.UserData.load_from_nickname(unix_nick)
		if udata:
			self.flash.msg = "Error: Nickname already taken"
			self.redirect('/first/visit/?taken&continue=%s' % continue_)
			return

		udata = stores.UserData.load()
		udata.nickname = nick
		udata.unix_nick = unix_nick
		udata.put()
		counter.Counter('TotalUsers').increment()

		self.flash.msg = "Welcome to Sybil, %s" % nick
		self.redirect(continue_)


# Map URLs to our RequestHandler classes above
_URLS = [
	('^/first/?', Index),
	('^/first/visit/?', FirstVisit),
]

def main():
	if not random.randint(0, 25):
		framework.profile_main(_URLS)
	else:
		framework.real_main(_URLS)

if __name__ == '__main__':
	main()
