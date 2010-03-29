#!/usr/bin/env python

import logging
import os

from google.appengine.api import memcache, datastore_errors
from google.appengine.ext import db

from common import const, utils

CURRENT_VERSION_ID = (lambda: os.environ.get('CURRENT_VERSION_ID','0'))
KEY_TEMPLATE = "memo(v=%s,k=%d|%s)"

class _SterileUrl(unicode): pass

def sterilize_url(url, *anti_args):
	"""
	Return the url void of arguments known to not affect the content of the page.


	Example:
		http://sybil.appspot.com/pakattack161?name=sybil&msg=Bacon+is+yummy!
		-> /pakattack161?name=sybil

	"""
	if isinstance(url, _SterileUrl):
		return url

	# *args variables are tuples and list+tuple doesn't work
	anti_args = list(anti_args)
	url = utils._filter_url(url, const.STERILIZED_ARGS+anti_args)
	if url[-1] in ['?', '&']:
		url = url[:-1]
	return _SterileUrl(url)

def paginate(self, prefix=''):
	"""Abstract pagination decorator

	Arguments:
		prefix: string. deliniate bookmarks in the url to support several
			paged data sets.

	Args to decoratee:
		limit: int. same as Query.fetch()
		offset: int. same as Query.fetch()
		bookmark: Key. Used in __key__ sorted queries to restart from the last
			entity in a given search (should be used with >=/<=).

	Returns (in a dict):
		results: list. of 'limit' entities from the query function
		page: int. current page index
		per_page: int. number of entities per page (a.k.a. limit)
		prev: Key. the bookmark this set of 1000 entities is keyed to
		next: Key. the new 'bookmark' for the next page.
	"""
	if prefix:
		prefix += '_'

	def decorator(fetch_func):
		def wrapper():
			offset = 0
			next = None
			bookmark = self.request.get(prefix+'bookmark', None)
			if bookmark is not None:
				try:
					bookmark = db.Key(bookmark)
				except datastore_errors.BadKeyError:
					logging.exception('Bookmark failed to keyify: %r(from %s)' %
									  (bookmark, prefix+'bookmark'))
					bookmark = None
			page = self.request.get_range(prefix+'page', min_value=1, default=1)
			per_page = self.request.get_range(prefix+'per_page', min_value=1,
											  max_value=25, default=6)

			# Handles the case where the user goes directly to a url
			# Any requests to a page that must display results beyond the first
			# 1000 are set back to 1000-per_page.
			if bookmark is None and page > 1:
				if (page * per_page) >= 1000:
					page = (1000 / per_page) - 1
					self.flash.msg = "Error loading direct link data. Resetting to page %d." % page
				offset = ((page - 1) * per_page)

			# Original recursion attempt that really isn't a good idea
			#if bookmark is None and page > 1:
			#	offset = ((page - 1) * per_page)
			#	if (page * per_page) >= 1000:
			#		results = fetch_func(limit=1, offset=999, bookmark=bookmark)
			#		if results:
			#			bookmark = results[0].key()
			#			offset = offset - 1000
			#		else:
			#			page = (1000 / per_page) - 1
			#			offset = ((page - 1) * per_page)
			#			self.flash.msg = "Error loading direct link data. Resetting to page %d." % page

			results = fetch_func(limit=per_page+1, offset=offset, bookmark=bookmark)
			if len(results) > per_page:
					next = results.pop().key()

			return {'results':results, 'page':page, 'per_page':per_page,
					'prev':bookmark, 'next':next}
		return wrapper
	return decorator

def learn(url, id, namespace='', skip=False, flush=False,
		  version=CURRENT_VERSION_ID(), version_key=None, ttl=0, del_ttl=0):
	"""
	Decorator to memoize url specific functions using the memcache.

	arguments:
	url		- The url containing the memoized data.
	id		- An identifier unique to the data being memoized.
	namespace   - Namespace of the cache. Specifically useful for /manage/
	skip	- Bypass the cache when retreiving data.
	flush 	- End with an empty cache.
	version	- Defaults to the app's current version.
	version_key - If not None it will attempt to load a version from the memcache.
	ttl		- Specifies timeout for setting memcache.
	del_ttl	- Specifies the timeout for deleting the memcache.

	"""
	# Load a version from the memcache
	# If there's no given version we'll use the passed version.
	if version_key is not None:
		version = memcache.get(version_key, namespace) or version
	cache_key = KEY_TEMPLATE % (
		version,
		hash(sterilize_url(url)),
		id
	)
	def decorator(func):
		def wrapper(*args, **kwargs):
			if skip:
				logging.debug("Skipping: %s(%s)" % (cache_key, url))
				data = None
			else:
				data = utils.deserialize_models(memcache.get(cache_key, namespace))

			if data is None:
				# The memcache was empty so we need to load the data even if
				# we're not going to store it.
				data = func(*args, **kwargs)
				if not flush:
					logging.debug("Memoizing: %s(%s)" % (cache_key, url))
					memcache.set(cache_key, utils.serialize_models(data), ttl)

			if flush and data:
				# Because we retrieved data we know we need to flush it.
				logging.debug("Flushing: %s(%s)" % (cache_key, url))
				memcache.delete(cache_key, seconds=del_ttl, namespace=namespace)
			return data
		return wrapper
	return decorator

def forget(url, id, namespace='', version=CURRENT_VERSION_ID, ttl=0):
	"""
	Prematurely delete a memoized entry.

	"""
	cache_key = KEY_TEMPLATE % (
		version,
		hash(sterilize_url(url)),
		id,
	)
	logging.debug("Clearing: %s(%s)" % (cache_key, url))
	return memcache.delete(cache_key, seconds=ttl, namespace=namespace)
