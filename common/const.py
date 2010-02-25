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

import	uuid

from	google.appengine.api	import users

_DEBUG = False
# Possible output types a page can have.
OUTPUT_TYPES = {
	'default':	{'header':'text/html; charset=utf-8', 'ext':'html'},
	'html': 	{'header':'text/html; charset=utf-8', 'ext':'html'},
	'xml': 		{'header':'application/xml; charset=utf-8', 'ext':'xml'},
	'feed':		{'header':'application/rss+xml; charset=utf-8', 'ext':'xml'},
	'atom':		{'header':'application/atom+xml; charset=utf-8', 'ext':'xml'},
	'rss':		{'header':'application/rss+xml; charset=utf-8', 'ext':'xml'},
	'json':		{'header':'application/json; charset=utf-8'},
}
# Args that are dropped from serilized urls.
_STERILIZED_ARGS = ['msg', 'msg_type', 'flush_cache', 'refresh_cache', 'output']

#Can be used to determine if udata exists.
#BOGUS_USER = users.User('bogus@example.com')

AVAILABLE_THEMES = ['framed', 'easter', 'sterile', 'grunge']
#[os.path.splitext(f)[0] for f in os.listdir(os.path.join('static', 'css'))]
#AVAILABLE_THEMES.remove('default')
AVAILABLE_THEMES.sort()

AVAILABLE_DESIGNS = ['original', 'elegance']
AVAILABLE_DESIGNS.sort()

CF_SCRIPTS = ['bubbles', 'aura', 'dreamtree', 'magictree', 'foggycity',
			  'pixels', 'starspiral', 'heart', 'eclipse', 'tulips', 'sandbox']
CF_SCRIPTS.sort()
# CF Script Credits
# Aura - "Things To Say" by Momo
#	background { b -0.2 sat 1 hue 90 }
# "Dream Tree" by Patrick Dietrich
# "Magic Tree" by Patrick Dietrich
# "Foggy City" by Meico
# "Pixels" by Altaco
# "Star Spiral" by Yon
# "Heart" by Artu
