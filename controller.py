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

import random

#import controllers
import controllers.about
import controllers.create
import controllers.custom
import controllers.discover
import controllers.firstvisit
import controllers.main
import controllers.manage
import controllers.tasks
import controllers.update
import controllers.worlds
import controllers.zipme
import lib.search

from common import framework

# Map URLs to our RequestHandler classes above
_URLS = [
	# about.py
	('^/about/', controllers.about.Index),
	('^/about/profile/', controllers.about.AboutProfile),
	('^/about/world/', controllers.about.AboutWorld),

	# create.py
	('^/create/profile/', controllers.create.NewProfile),
	('^/create/comment/', controllers.create.NewComment),
	('^/create/world/', controllers.create.NewWorld),
	('^/create/', controllers.create.Index),

	# custom.py
	('^/custom/theme/?', controllers.custom.CustomTheme),
	('^/custom/cf_script/?', controllers.custom.CustomCFScript),

	# discover.py
	('^/discover/profiles/', controllers.discover.DiscoverProfile),
	('^/discover/profiles/rss/', controllers.discover.ProfileFeed),
	('^/discover/worlds/', controllers.discover.DiscoverWorld),
	('^/discover/worlds/rss/', controllers.discover.WorldFeed),
	('^/discover/', controllers.discover.Index),

	# firstvisit.py
	('^/first/', controllers.firstvisit.Index),
	('^/first/visit/', controllers.firstvisit.FirstVisit),

	# manage.py
	('^/manage/?', controllers.manage.Index),
	('^/manage/update/([^\/]+)/', controllers.manage.UpdateSingle),
	('^/manage/update/', controllers.manage.Update),
	('^/manage/edit/', controllers.manage.Edit),
	('^/manage/dismiss/', controllers.manage.Dismiss),

	# update.py
	('^/update/count/([^/]+)/(?:([^/]+)/)?', controllers.update.Count),
	('^/update/([^/]+)/', controllers.update.Index),

	# tasks.py
	('^/tasks/world/([^/]+)/(?:([^/]+)/)?', controllers.tasks.WorldWorker),
	('^/tasks/logging/', controllers.tasks.LoggingWorker),
	('^/tasks/searchindexing/', lib.search.SearchIndexing),

	# worlds.py
	('^/world/edit/([^/]+)/', controllers.worlds.Edit),
	('^/world/delete/', controllers.worlds.Delete),
	('^/world/join/', controllers.worlds.Join),
	('^/world/leave/', controllers.worlds.Leave),
	('^/world/(?:([^/]+)/)?', controllers.worlds.Index),


	# zipme.py
	('/src.zip', controllers.zipme.ZipMaker),

	# main.py
	('^/', controllers.main.Index),
	('^/changelog/', controllers.main.ChangeLog),
	('^/env/', controllers.main.PrintEnviron),
	('^/([^/]+)/(rss|atom|feed)/', controllers.main.UserFeed),
	('^/([^/]+)/([^/]+)/edit/', controllers.main.EditProfile),
	('^/([^/]+)/([^/]+)/delete/', controllers.main.DeleteProfile),
	('^/([^/]+)/([^/]+)/', controllers.main.ViewProfile),
	('^/([^/]+)/', controllers.main.ViewUser),
]

def main():
	if not random.randint(0, 25):
		framework.profile_main(_URLS)
	else:
		framework.real_main(_URLS)

if __name__ == '__main__':
	main()
