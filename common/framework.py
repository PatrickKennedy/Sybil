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

import datetime
import logging
import os
import random
import sys
import urllib
import urlparse

from google.appengine.api	import users, memcache
from google.appengine.ext	import webapp
from google.appengine.ext.webapp	import template

from common	import const, counter, flash, utils
from common.stores	import UserData
from common.templatefilters	import register_filters
from lib import datastore_cache


sys.path.insert(0, os.path.join('lib', 'docutils-0.6-py2.5-win32.egg'))
sys.path.insert(0, os.path.join('lib', 'Jinja2-2.3.1-py2.5-win32.egg'))
sys.path.insert(0, os.path.join('lib', 'simplejson-2.0.9-py2.5-win32.egg'))


#webapp.template.register_template_library('common.templatefilters')
#webapp.template.register_template_library('django.contrib.markup.templatetags.markup')

#datastore_cache.DatastoreCachingShim.Install()


try:
	import jinja2
except:
	pass

try:
	ultracache
except:
	ultracache = {}

class TemplateRenderer(object):
	def __init__(self, template_path, context={}, output='html'):
		output_info = const.OUTPUT_TYPES[output]

		if not isinstance(template_path, list):
			template_path = [template_path]

		# Format the last item of the path into a filename.
		template_name = "%s.%s" % (template_path.pop().lower(), output_info['ext'])
		path_ = []
		path_.append(os.path.join('.', 'templates_compiled'))
		path_.append(os.path.join('.', 'templates_compiled', *template_path))
		path_.append(os.path.join('.', 'templates'))
		path_.append(os.path.join('.', 'templates', *template_path))
		path_.append(template_name)

		self.path_ = path_
		self.context = context

	def render(self):
		if not hasattr(self, '__rendered'):
			renderer = self.render_jinja
			self.__rendered = renderer(self.path_, self.context)
		return self.__rendered

	def render_jinja(self, path_, context):
		class DjangoUndefined(jinja2.Undefined):
			def __get__(*args, **kwargs): return ''
			def __getattr__(*args, **kwargs): return ''
			def __getitem__(*args, **kwargs): return ''

		class PythonLoader(jinja2.FileSystemLoader):
			def load(self, environment, name, globals=None):
				"""Loads a Python code template."""
				if globals is None:
					globals = {}
				code = ultracache.get(name.encode("base64"), None)
				if code is None:
					code, filename, uptodate = self.get_source(environment, name)
					if not code.startswith("from __future__"):
						code = environment.compile(code, name, filename)
					else:
						# Quick and dirty fix to get the code to compile
						# TODO: Recompile with correct line endings
						code = code.replace('\r\n', '\n')
						code = compile(code, filename, 'exec')
				ultracache[name.encode("base64")] = code
				return environment.template_class.from_code(environment, code,
															globals)

		env = jinja2.Environment(
			loader = PythonLoader(path_[:-1]),
			undefined = DjangoUndefined,
		)
		register_filters(env)
		template = env.get_template(path_[-1])
		content = template.render(context)
		#logging.info("Rednering %s" % path_[-1])
		return content

	def render_django(self, path_, context):
		return template.render(os.path.join(*path_), context, debug=const._DEBUG)

class Lazy(object):
	"""@Lazy

	Converts a function into a lazy property. Replaces the property with the
	return value of function.

	To reset the cache just delete the property.

	"""
	def __init__(self, calculate_function):
		self._calculate = calculate_function

	def __get__(self, obj, _=None):
		if obj is None:
			return self
		value = self._calculate(obj)
		setattr(obj, self._calculate.func_name, value)
		return value

class BaseRequestHandler(webapp.RequestHandler):
	# Define global session variables to reduce the amount of reprocessing (eg.
	# when loading the UserData object) and increase accessibility within the
	# code (eg. self.context makes for much cleaner code rather than passing a
	# context in every function call).
	#
	# The following basically mimics __init__; however, because not all the
	# handler's variables are defined in __init__ (eg. self.request), overwriting
	# __init__ is impractical.
	@Lazy
	def context(self):	return {}
	@Lazy
	def flash(self):	return flash.Flash()
	@Lazy
	def referer(self):	return self.request.headers.get('REFERER', '/')
	@Lazy
	def url(self):		return self.request.url
	@Lazy
	def user(self):		return users.get_current_user()
	@Lazy
	def udata(self):	return UserData.load()

	def render(self, template_path, extra_context={}, output='html'):
		"""render(template_path, extra_context={}, output='html') -> None

		Render the given template with the extra (optional) values and write it
		to the response.

		Args:

		template_path
			str, list - The template to render.

		extra_context
			dict - Template values to provide to the template.

		output
			str - The outputed page type.
			Only supports 'html'

		Return:

		None

		"""

		output_info = const.OUTPUT_TYPES[output]

		parsed	= urlparse.urlparse(self.request.url)

		get 	= self.request.get
		user	= self.user
		udata	= self.udata

		# We want to force the user to give themself a nickname
		# But it will fall into an infinate loop before the user can submit a name.
		if udata and not udata.nickname and not parsed.path.startswith('/first/'):
			self.redirect('/first/?continue=%s' % self.url)
			return

		cf_credit = ''
		cf_script = get('cf_script', '')
		use_custom_cf = False
		if cf_script:
			pass
		elif udata:
			if udata.use_custom_cf:
				use_custom_cf = True
				cf_script = udata.custom_cf_script
			elif udata.cf_script != 'disabled':
				cf_script = udata.cf_script
		else:
			cf_script = 'daze'

		if not use_custom_cf:
			path = os.path.join('.', 'data', 'contextfree', '%s.txt' % cf_script.lower())
			if cf_script and os.path.exists(path):
				with open(path) as f:
					cf_credit = f.readline()
					cf_script = f.read()

		msg_count = None
		if udata:
			msg_count = counter.Counter('%sMessages' % udata.key_name).count

		# Allow forced message overrides
		msg = get('msg')
		if msg:
			self.flash.msg = msg

		context = {
			'cf_credit'	: cf_credit,
			'cf_script'	: cf_script,
			'debug'		: get('debug'),
			'flash'		: self.flash,
			'host_url'	: "%s://%s" % (parsed.scheme, parsed.hostname),
			'is_dev'	: utils.is_dev(),
			'login_url'	: users.create_login_url('/first/?continue=%s' % self.url),
			'logout_url': users.create_logout_url('/'),
			'msg_count'	: msg_count,
			'page_admin': users.is_current_user_admin(),
			'request'	: self.request,
			'search_q'	: get('q'),
			'design'	: get('design'),
			'theme'		: get('theme'),
			'udata'		: udata,
			'url'		: self.url,
			'user'		: user,
			'year'		: datetime.datetime.now().year
		}
		context.update(extra_context)
		context.update(self.context)

		if get('json', False) is False:
			renderer = TemplateRenderer(template_path, context, output)
			rendered = renderer.render()
		else:
			const.OUTPUT_TYPES['json']
			import simplejson
			rendered = simplejson.dumps(context, skipkeys=True).replace('\\n', '\n')

		self.response.headers['Content-Type'] = output_info['header']
		self.response.headers['Content-Length'] = str(len(rendered))
		self.response.out.write(rendered)

	def args_to_dict(self, **extra_args):
		"""Converts the URL and POST parameters to a singly-valued dictionary.

		Returns:
			dict with the URL and POST body parameters
		"""
		req = self.request
		dict_ = dict([(arg, req.get(arg)) for arg in req.arguments()])
		dict_.update(extra_args)
		return dict_

	def args_to_url(self, **extra_args):
		"""args_to_url(**extra_args) -> str

		Conevrts the URL and POST params to a string which can be placed at the
		end of a redirect to persist values.

		Any extra params can be passed as keyword arguments which will be added
		to the end of the list.

		"""

		# Equivilant to what we have below.
		return self.filter_args(extra_args.keys(), **extra_args)

		arg_list = []
		req = self.request
		for arg in self.request.arguments():
			value = self.request.get(arg, '').strip()
			if value:
				arg_list.append('%s=%s' % (arg, urllib.quote_plus(value)))
		for arg, value in extra_args.items():
			arg_list.append('%s=%s' % (arg, urllib.quote_plus(value)))

		return '?' + '&'.join(arg_list)


	def filter_args(self, args, exclusive=False, **extra_args):

		req = self.request
		return utils._filter_args([(arg,'=',req.get(arg)) for arg in req.arguments()],
			args, exclusive, **extra_args)

	def filter_url(self, args, exclusive=False, **extra_args):

		return utils._filter_url(self.url, args, exclusive, **extra_args)

	def display_error(self, message, **kwargs):
		"""Shows an error HTML page.

		Args:
		  message: string
		  A detailed error message.
		"""
		args = self.args_to_dict()
		args.update(kwargs)
		args = pprint.pformat(args)
		self.render('error', locals())
		logging.error(message)

	def get_name_list(self, quantity, len_):
		"""get_name_list(int quantity, int len_) -> list<str>

		Generates `quantity` random names and returns them as a list of strings.

		If len_ is greater than 10 it will be set to 10.

		"""

		names = []
		append = names.append
		choice = random.choice
		join = os.path.join

		# Limit the length so the user can't create an infinate loop.
		if len_ > 10:
			len_ = 10
		# If the number is odd then make the prefix the longer item.
		if (len_ % 2):
			prefix_len = (len_ + 1) / 2
			suffix_len = (len_ - 1) / 2
		else:
			prefix_len = suffix_len = (len_ / 2)

		name_files = os.listdir(join('.', 'data'))
		name_files = [file_ for file_ in name_files if file_.startswith('names')]
		fn = choice(name_files)
		sn = choice(name_files)
		with open(join('.', 'data', fn)) as f:
			firstnames = f.readlines()

		with open(join('.', 'data', sn)) as f:
			surnames = f.readlines()

		def mid_(quantity, list_):
			"""Return a point within a safe zone of indexes"""
			return random.randrange(int(quantity/2.0), len(list_)-int(quantity/2.0))
		def range_(mid):
			return range((mid-(quantity/2)), int(round(mid+(quantity/2.0))))
		def map_(x, y):
			if not random.randint(0, 2) and False:
				prefix = x[-prefix_len:]
			else:
				prefix = x[:prefix_len]
			if not random.randint(0, 2) and False:
				suffix = y[-suffix_len:]
			else:
				suffix = y[:suffix_len]
			return (prefix+suffix).capitalize()


		r = range_(mid_(quantity, firstnames))
		firstnames = firstnames[r[0]-1:r[-1]]
		r = range_(mid_(quantity, surnames))
		surnames = surnames[r[0]-1:r[-1]]

		try:
			names = map(map_, firstnames, surnames)
		except TypeError:
			logging.debug('get_name_list information/n'
						  'lengths - prefix: %d | suffix: %d ' % (prefix_len, suffix_len)+
						  'names -\n\tfirst names: %s\n\tsur names: %s' % (firstnames, surnames))

		return names

	def page_admin(self, user):
		"""page_admin(* user) -> bool

		Return True if `user` matches the current user or
		if current user is an admin.

		Accepts a string or users.User.

		"""

		if isinstance(user, basestring):
			user = UserData.load_from_nickname(recipient)

		if user == self.user or users.is_current_user_admin():
			return True

		return False


#def main(urls):
#	real_main(urls) if random.randint(0, 25) else profile_main(urls)

#def real_main(urls):
def main(urls):
	from google.appengine.ext.webapp.util import run_wsgi_app

	application = webapp.WSGIApplication(urls, debug=const._DEBUG)
	run_wsgi_app(application)

def profile_main(urls):
	# This is the main function for profiling
	# We've renamed our original main() above to real_main()
	import cProfile, pstats, StringIO
	prof = cProfile.Profile()
	prof = prof.runctx("real_main(urls)", globals(), locals())

	stream = StringIO.StringIO()
	stats = pstats.Stats(prof, stream=stream)
	stats.sort_stats("time")  # Or cumulative
	stats.print_stats(80)  # 80 = how many to print
	# The rest is optional.
	# stats.print_callees()
	# stats.print_callers()
	logging.info("Profile data:\n%s", stream.getvalue())


"""
Dear Lily, (or do you go by Alyssa now?)

  Originally this letter was to accompany a postcard and pair of socks, but,
alas, international shipping got the best of me. However, I'd hate to delay this
letter longer than necessary. You see, I long to make amends for the
circumstances that sent us our separate ways some two years ago. I surprised
myself at just how hard I took the news that decided you were a lesbian, not to
mention how bitter I became. I want you to know how deeply I regret the pain I
caused. I hope you can forgive me for that. I would love to hear from you again,
but even if I never do, I want you to know I hope and pray the best for your life.

Yours truly,
  Patrick
"""
