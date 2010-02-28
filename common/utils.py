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

import logging
import os
import re
import urllib
import urlparse

from  google.appengine.api import users, memcache
from  google.appengine.ext import db, webapp
from  google.appengine.datastore import entity_pb

replace_spaces = re.compile('[\s+]')
strip_nonletters = re.compile('[^a-zA-Z0-9.\-_]+')

def is_dev():
	"""is_dev() -> bool

	Return true if running on the development server.

	"""
	return os.environ['SERVER_SOFTWARE'].startswith('Dev')

def word_count(*strs):
	count = 0
	for s in strs:
		# We add 1 because "the lazy dog" has 2 spaces but 3 words.
		count += s.count(' ') + 1
		count += s.count('\n\n') if '\n\n' in s else s.count('\n')
	return count

def unix_string(s):
	s = s.lower()
	s = replace_spaces.sub('_', s)
	s = strip_nonletters.sub('', s)
	return s

def get_current_user():
	"""get_current_user() -> users.User

	Return a lowercase based User object build from the current user.

	"""
	return users.get_current_user()

	user = users.get_current_user()
	if not user:
		return user
	return get_user(user.nickname().lower())

def serialize_models(models):
	if models is None:
		return None
	elif isinstance(models, db.Model):
		# Just one instance
		return db.model_to_protobuf(models).Encode()
	return [db.model_to_protobuf(x).Encode() for x in models]

def deserialize_models(data):
	if data is None:
		return None
	elif isinstance(data, str):
		# Just one instance
		return db.protobuf_to_model(entity_pb.EntityProto(data))
	return [db.model_from_protobuf(entity_pb.EntityProto(x)) if x is not None else None for x in data]


def page_admin(user):
	"""page_admin(* user) -> bool

	Return True if `user` matches the current user or
	if current user is an admin.

	Accepts a string or users.User.

	"""

	if isinstance(user, basestring):
		user = users.User(user)

	if user == users.get_current_user() or users.is_current_user_admin():
		return True

	return False

def build_url(url, **new_args):
	url_tuple = urlparse(url)
	url_without_args = '%s://%s%s' % (url_tuple.scheme, url_tuple.hostname,
									  url_tuple.path)

	args = {}
	for arg in url_tuple[4].split('&'):
		if '=' in arg:
			args.__setitem__(*arg.split('=', 1))
	args.update(new_args)
	params = ['%s=%s' % (key, value) for (key, value) in args.iteritems()]

	logging.info('utils.build_url(url=%s, args=%s)' % (url, args))

	return '%s?%s' % (url_without_args, '&'.join(params))

def _filter_args(args, anti_args, exclusive=False, **extra_args):
	"""Filter the current URL and return a str of args.

	Parameters::
	args
		A list of arg names.
	exclusive
		If True the url will have only the args given.
	extra_args
		Any kwargs passed will be added to the url.

	Return::
	Filtered args in string form

	For example, if your URL is ``/search?q=foo&num=100&start=10``, then

	   ``self.filter_args(['start'])`` -> ``?q=foo&num=100``
	   ``self.filter_args(['q'], True, a="bar")`` -> ``?q=foo&a=bar``
	   ``self.filter_args(['random'], True)`` -> ``?``

	"""

	queries = []

	if isinstance(args, basestring):
		url = urlparse.urlparse(args)
		if url.path.count('='):
			arg_str = url.path
		else:
			arg_str = url.query
		args = [x.partition('=') for x in arg_str.split('&') if x]

	for arg, sep, value in args:
		# If exclusive, we only want args given,
		# other wise we don't want any args listed.
		# Also, if the user passes the arg in the dictionary, skip it here.
		if (exclusive and arg not in anti_args) or (arg in anti_args) or \
			 (arg in extra_args):
			 continue

		# No longer escaping the value unless problems arise.
		#queries.append('%s%s%s' % (arg, sep, urllib.quote_plus(value)))
		queries.append('%s%s%s' % (arg, sep, value))

	for arg, value in extra_args.iteritems():
		sep = value and '=' or ''
		queries.append('%s%s%s' % (arg, sep, urllib.quote_plus(value)))

	return '?' + '&'.join(queries)


def _filter_url(url, anti_args, exclusive=False, **extra_args):
	"""_filter_url(url: str, anti_args: list, exclusive=False: bool, **extra_args) -> str

	Filters the current URL to only have the given list of arguments.
	args 		- A list of arg names.
	exclusive	- If True the url will have only the args given.
	extra_args	- Any kwargs passed will be added to the url.

	For example, if your URL is /search?q=foo&num=100&start=10, then

	   self.filter_url(['start']) => /search?q=foo&num=100
	   self.filter_url(['q'], True, a="bar") => /search?q=foo&a=bar
	   self.filter_url(['random'], True) => /search?

	"""

	url = urlparse.urlparse(url)

	return '%s%s' % (url.path, _filter_args(url.query, anti_args, exclusive, **extra_args))
