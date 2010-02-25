#!/usr/bin/env python
#
import code
import getpass
import os
import sys
import re

# Hardwire in appengine modules to PYTHONPATH
# or use wrapper to do it more elegantly
appengine_dirs = ['C:/Programming/google_appengine',
				  'C:/Programming/google_appengine/lib/django',
				  'C:/Programming/google_appengine/lib/webob',
				  ]
sys.path.extend(appengine_dirs)
# Add your models to path
my_root_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, my_root_dir)

from google.appengine.ext import db
from google.appengine.ext.remote_api import remote_api_stub

from common import stores

APP_NAME = 'sybil'

def auth_func():
 return (raw_input('Username:'), getpass.getpass('Password:'))

# Use local dev server by passing in as parameter:
# servername='localhost:8080'
# Otherwise, remote_api assumes you are targeting APP_NAME.appspot.com
remote_api_stub.ConfigureRemoteDatastore(APP_NAME, '/remote_api', auth_func)

# Do stuff like your code was running on App Engine

class Mapper(object):
	# Subclasses should replace this with a model class (eg, model.Person).
	KIND = None

	# Subclasses can replace this with a list of (property, value) tuples to filter by.
	FILTERS = []

	def map(self, entity):
		"""Updates a single entity.

		Implementers should return a tuple containing two iterables (to_update, to_delete).
		"""
		return ([], [])

	def get_query(self):
		"""Returns a query over the specified kind, with any appropriate filters applied."""
		q = self.KIND.all()
		for prop, value in self.FILTERS:
			q.filter("%s =" % prop, value)
		q.order("__key__")
		return q

	def run(self, batch_size=100):
		"""Executes the map procedure over all matching entities."""
		q = self.get_query()
		entities = q.fetch(batch_size)
		while entities:
			to_put = []
			to_delete = []
			for entity in entities:
				map_updates, map_deletes = self.map(entity)
				to_put.extend(map_updates)
				to_delete.extend(map_deletes)
			if to_put:
				db.put(to_put)
			if to_delete:
				db.delete(to_delete)
			q = self.get_query()
			q.filter("__key__ >", entities[-1].key())
			entities = q.fetch(batch_size)



class BulkDeleter(Mapper):
	def __init__(self, kind, filters=None):
		self.KIND = kind
		if filters:
			self.FILTERS = filters

	def map(self, entity):
		return ([], [entity])

if false:
	rest_url = re.compile('`([^<]+)<([^>]+)>`_')
	rest_ref = re.compile('([^_\s`]+_)')
	objs = stores.Profile.all().fetch(100)
	for obj in objs:
		for text in [obj.common, obj.links, obj.apperence, obj.background, obj.extra_info]:
			text = rest_url.sub('"\1":\2', text)
			if rest_url.findall(text) or rest_ref.findall(text):
				print obj.name
	#db.puts(objs)

if __name__ == "__main__":
	code.interact('App Engine interactive console for %s' % (app_id,), None, locals())

