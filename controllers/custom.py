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

from	google.appengine.api		import datastore
from	google.appengine.ext		import webapp
from	google.appengine.ext.db		import Query

from	common			import framework, const, utils
from	common.stores	import UserData, Profile, WorldMember, Message

class CustomTheme(framework.BaseRequestHandler):
	def get(self):
		user		= utils.get_current_user()
		udata		= UserData.load(user)

		context = {
			'udata': udata,
		}

		self.render(['custom', 'customtheme'], context)

	def post(self):
		user		= utils.get_current_user()
		udata		= UserData.load(user)
		action		= self.request.get('action', 'Cancel')
		custom_theme = self.request.get('custom_css', '')

		msg = "Changes to theme discarded"
		if action == 'Save':
			udata.custom_css = custom_theme
			udata.put()
			msg = "Theme Saved"

		self.flash.msg = msg
		self.redirect('/manage/')

class CustomCFScript(framework.BaseRequestHandler):
	def get(self):
		user		= utils.get_current_user()
		udata		= UserData.load(user)

		context = {
			'udata': udata,
		}

		self.render(['custom', 'customcfscript'], context)

	def post(self):
		from	google.appengine.ext.webapp	import template

		user		= utils.get_current_user()
		udata		= UserData.load(user)
		action		= self.request.get('action', 'Cancel')
		cf_script = self.request.get('cf_script', '')

		if action == "Preview":
			context = {
				'cf_script': cf_script
			}

			t = template.Template("""<html>
<head>
<title>ContextFree Script Preview</title>
<script src="/js/jquery.js" type="text/javascript"></script>
<script src="/js/contextfree.js" type="text/javascript"></script>
<script src="/js/dynamicbg.js" type="text/javascript"></script>
</head>
<body>
<div id="cf_script" style="display:none;" />{{ cf_script }}</div>
<script>display();</script>
</body>
</html>""")
			self.response.out.write(t.render(context))
			return

		msg = "Changes to ContextFree Script discarded"
		if action == 'Save':
			udata.custom_cf_script = cf_script
			udata.put()
			msg = "ContextFree Script Saved"

		self.flash.msg = msg
		self.redirect('/manage/')


# Map URLs to our RequestHandler classes above
_URLS = [
  ('^/custom/theme/?', CustomTheme),
  ('^/custom/cf_script/?', CustomCFScript),
]

def main():
	if not random.randint(0, 25):
		framework.profile_main(_URLS)
	else:
		framework.real_main(_URLS)

if __name__ == '__main__':
	main()
