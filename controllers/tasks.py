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
import sys
import traceback
import urllib
import urlparse

from urllib	import quote_plus

from google.appengine.api.labs	import taskqueue
from google.appengine.api		import capabilities, datastore, memcache, users
from google.appengine.ext		import db, webapp
from google.appengine.runtime	import apiproxy_errors

from common			import counter, framework, stores, utils

class WorldWorker(framework.BaseRequestHandler):
	def post(self, action, sub_action=''):
		func_name = action.lower() + ('_%s' % sub_action.lower() if sub_action else '')
		if hasattr(self, func_name):
			getattr(self, func_name)()

	def add_member(self):
		udata = db.get(self.request.get('udata'))
		world = db.get(self.request.get('world'))

		key_name = stores.WorldMember.key_name_form % (world.key_name, udata.key_name)
		def txn():
			member = WorldMember(key_name=key_name, user=udata, world=world)
			member.put()
			return True

		if db.run_in_transaction(txn):
			framework.unmemoize(world.url, 'member_listing')

class LoggingWorker(framework.BaseRequestHandler):
	def post(self):
		logging.info("LOGGING WORKER:\n%s" % pprint.pformat(os.environ))

_URLS = [
	#('^/tasks/profile/?', ProfileWorker),
	#('^/tasks/comment/?', CommentWorker),
	('^/tasks/world/([^/]+)/(?:([^/]+)/)?', WorldWorker),
	('^/tasks/logging/', LoggingWorker),
]

def main():
	if not random.randint(0, 25):
		framework.profile_main(_URLS)
	else:
		framework.real_main(_URLS)

if __name__ == '__main__':
  main()
