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
import	random

from	google.appengine.ext	import webapp

from	common		import const, framework

class Index(framework.BaseRequestHandler):
	def get(self):
		msg = self.request.get('msg')
		msg_type = self.request.get('msg_type', 'info')
		self.render(['index', 'indexAbout'], locals())

class AboutProfile(framework.BaseRequestHandler):
	def get(self):
		msg = self.request.get('msg')
		msg_type = self.request.get('msg_type', 'info')
		self.render(['about', 'aboutProfile'], locals())

class AboutWorld(framework.BaseRequestHandler):
	def get(self):
		msg = self.request.get('msg')
		msg_type = self.request.get('msg_type', 'info')
		self.render(['about', 'aboutWorld'], locals())


# Map URLs to our RequestHandler classes above
_URLS = [
  ('^/about/?', Index),
  ('^/about/profile/?', AboutProfile),
  ('^/about/world/?', AboutWorld),
]

def main():
	if not random.randint(0, 25):
		framework.profile_main(_URLS)
	else:
		framework.real_main(_URLS)

if __name__ == '__main__':
	main()
