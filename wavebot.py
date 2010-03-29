import os
import logging

from google.appengine.api import memcache, users
from google.appengine.ext import db

from waveapi import document
from waveapi import events
from waveapi import model
from waveapi import robot

from common import const, framework, memopad, stores, utils

ROBOT_NAME = 'sybil-labs'
ROBOT_ADDRESS = '%s@appspot.com' % ROBOT_NAME
ROBOT_URL = 'http://%s.appspot.com' % ROBOT_NAME

MSG_NEW_USER = """
Have we met? I see here your address is %s.
In order to use me you must link your Wave address with your Sybil account
You may use this link to quickly perform that change:
http://%s.appspot.com/manage/update/wave_address/?value=%s
"""

MSG_OLD_USER = """
Hey, I know you! You're %s!
"""

MSG_HOWTO = u"""
How to use me:
Make the wave's title the name of the profile you want to load.
Changing the title will erase the current profile and load a new one.

Each attribute is displayed in it's own inline message.
Any changes to these messages will be reflected on Sybil.
The pips surrounding an attribute toggle between \u25aa and \u25ab when a change has successfully been saved.
NOTE: The first line of each mssage is the attribute name. DO NOT change this line.

Everything should be automatic, but these are here incase something breaks:
"""

class Caretaker(object):
	"""Manages a given event's state"""

	@framework.Lazy
	def udata(self): return stores.UserData.all().filter('wave_address =', self.creator).get()

	def __init__(self, properties, context):
		self.properties = properties
		self.context = context
		self.wavelet = context.GetRootWavelet()
		self.root_blip = context.GetBlipById(self.wavelet.GetRootBlipId())
		self.creator = self.wavelet.GetCreator()

	def on_robot_added(self):
		"""Invoked when the robot has been added."""
		creator = self.creator
		root_blip = self.root_blip
		udata = stores.UserData.all().filter('wave_address =', creator).get()
		if udata:
			root_blip.document.AppendText(MSG_OLD_USER % udata.nickname)
			doc = root_blip.document.GetText()

			# Bold user name
			loc = doc.find(udata.nickname)
			r = document.Range(loc, loc+len(udata.nickname)+1)
			root_blip.document.SetAnnotation(r, 'style/fontWeight', 'bold')

		else:
			root_blip.document.AppendText(MSG_NEW_USER % (creator, ROBOT_NAME, creator))
			doc = root_blip.document.GetText()

			# Highlight the user's Wave Address
			loc = doc.find(creator)
			r = document.Range(loc, loc+len(creator) + 1)
			root_blip.document.SetAnnotation(r, 'style/fontWeight', 'bold')

			# Linkify the URL
			url = 'http://%s.appspot.com/manage/update/wave_address/?value=%s' % (ROBOT_NAME, creator)
			r = document.Range(doc.find(url), len(url)+1)
			root_blip.document.SetAnnotation(r, 'link/manual', url)


		root_blip.document.AppendText(MSG_HOWTO)
		doc = root_blip.document.GetText()

		# General formatting
		loc = doc.find('How to use me:')
		r = document.Range(loc, loc+len('How to use me:')+1)
		root_blip.document.SetAnnotation(r, 'style/fontWeight', 'bold')

		root_blip.document.AppendElement(
			document.FormElement(
				document.ELEMENT_TYPE.BUTTON,
				'clear_profile',
				value="Clear Profile"
			)
		)
		root_blip.document.AppendElement(
			document.FormElement(
				document.ELEMENT_TYPE.BUTTON,
				'load_profile',
				value="Load Profile"
			)
		)

		self.wavelet.SetDataDocument('current_title', self.wavelet.title)
		if self.wavelet.title:
			self.on_title_change(wavelet)

	def on_title_change(self, wavelet=None):
		if wavelet is None:
			wavelet = self.context.GetWaveletById(properties['waveletId'])

		#TODO: Remove when swapping profiles in a single wave is possible.
		# Sybil can't erase a previous profile's blips and create new ones
		# making swapping profiles a bad idea.
		#if wavelet.GetDataDocument('profile_key_name'):
		#	return

		self.clear_profile(wavelet)
		profile = self.fetch_profile(self.creator, wavelet.title)
		if profile:
			self.write_profile(profile)
		else:
			url = 'http://%s.appspot.com%s' % (
				ROBOT_NAME,
				const.URL_PATTERNS['profile'] % (
					self.udata.nickname, utils.unix_string(wavelet.title)
				)
			)

			blip = self.root_blip.CreateChild()
			blip.document.AppendText("Cannot find %s. Please verify the profile exists at %s." % (wavelet.title, url))

			# Highlight profile name
			doc = blip.document.GetText()
			loc = doc.find(wavelet.title)
			r = document.Range(loc, loc+len(wavelet.title))
			blip.document.SetAnnotation(r, 'style/fontWeight', 'bold')

			# Linkify
			doc = blip.document.GetText()
			loc = doc.find(url)
			r = document.Range(loc, loc+len(url))
			blip.document.SetAnnotation(r, 'link/manual', url)

		wavelet.SetDataDocument('current_title', wavelet.title)
		return
		wavelet.CreateBlip().document.SetText(
			'Title: %s\nCreator: %s\nudata: %s\n\nProperties: %s' % (
				wavelet.title, self.creator, udata, properties
			)
		)

	def on_blip_change(self):
		wavelet = self.wavelet
		#TODO: Remove this when Wave begins sending WAVELET_TITLE_CHANGED events.
		if wavelet.title != wavelet.GetDataDocument('current_title'):
			logging.info('handling a changed title')
			self.on_title_change(wavelet)
			return

		blip = self.context.GetBlipById(self.properties['blipId'])
		if blip.creator == ROBOT_ADDRESS:
			key_name = wavelet.GetDataDocument('profile_key_name')
			text = blip.document.GetText()
			attr, _, value = text.partition('\n')
			pip = attr[-1]
			attr = attr[1:-1].lower()
			def txn():
				profile = stores.Profile.get_by_key_name(key_name)
				setattr(profile, attr, value)
				profile.put()

			if attr in stores.Profile.properties():
				# The user can't change this on the site, so we'll revert it
				# here to avoid confusion
				if attr == 'name':
					loc = len(attr)+3
					r = document.Range(loc, loc+len(blip.document.GetText()))
					blip.document.SetTextInRange(r, profile.name)
				else:
					db.run_in_transaction(txn)
					blip.document.SetText(text.replace(pip, [u'\u25aa', u'\u25ab'][pip ==  u'\u25aa']))
					#blip.document.SetText(text.replace(pip, ['~', '-'][pip ==  '~']))
					blip.document.SetAnnotation(document.Range(1, len(attr)+1),
											'style/fontWeight', 'bold')
					memopad.forget('/', 'profile_listing')

	def on_button_click(self):
		wavelet = self.wavelet
		logging.info('Pressed Button(%s)' % self.properties['button'])
		if self.properties['button'] == 'clear_profile':
			self.clear_profile(wavelet)
		elif self.properties['button'] == 'load_profile':
			key_name = wavelet.GetDataDocument('profile_key_name')
			if key_name:
				profile = stores.Profile.get_by_key_name(key_name)
			else:
				profile = self.fetch_profile(wavelet.creator, wavelet.title)

			if profile:
				self.write_profile(profile)
			else:
				logging.info('No such profile: %s' % wavelet.title)
				wavelet.CreateBlip().document.SetText('No such profile: %s' % wavelet.title)

	def fetch_profile(self, creator, name):
		udata = self.udata
		if udata:
			key_name = stores.Profile.key_name_form % (
				utils.unix_string(name), udata.key_name)
			profile = stores.Profile.get_by_key_name(key_name)
		else:
			profile = None
		return profile

	def write_profile(self, profile):
		if profile is None:
			return

		logging.info('writing profile')
		# Save blips for future deleting
		blips = []
		sub_blip = self.root_blip.CreateChild()
		for attr in [
			'age', 'gender', 'race', 'height', 'weight',
			'apperence', 'background', 'extra_info', 'links', 'common'
		]:
			blip = sub_blip.document.AppendInlineBlip()
			#blip = sub_blip.CreateChild()
			#blip = wavelet.CreateBlip()
			attr_range = document.Range(1, len(attr)+1)
			blip.document.SetText(u'\u25aa%s\u25aa\n%s' %(attr, getattr(profile, attr, '')))
			blip.document.SetAnnotation(attr_range, 'style/fontWeight', 'bold')
			blips.append(blip.blipId)

			doc_length = len(sub_blip.document.GetText())
			attr_range = document.Range(doc_length, doc_length+len(attr)+1)
			sub_blip.document.AppendText(attr)
			sub_blip.document.SetAnnotation(attr_range, 'style/fontWeight', 'bold')

		self.wavelet.SetDataDocument('profile_key_name', profile.key_name)
		#TODO: Reenable when the blip creator builds a real ID
		#wavelet.SetDataDocument('profile_blips', '||'.join(blips))

	def clear_profile(self, wavelet=None):
		logging.info('clearing previous blips')
		#TODO: Remove this when robot created blip ids link with actual blips
		for blip in self.context.blips.values():
			if blip.creator == ROBOT_ADDRESS:
				blip.Delete()
		return


		if wavelet is None:
			wavelet = self.wavelet

		for blipId in wavelet.GetDataDocument('profile_blips', '').split('||'):
			blip = self.context.GetBlipById(blipId)
			if blip:
				blip.Delete()



def on_button_click(properties, context):
	caretaker = Caretaker(properties, context)
	caretaker.on_button_click()

def on_robot_added(properties, context):
	caretaker = Caretaker(properties, context)
	caretaker.on_robot_added()

def on_title_change(properties, context):
	caretaker = Caretaker(properties, context)
	caretaker.on_title_change()

def on_blip_change(properties, context):
	caretaker = Caretaker(properties, context)
	caretaker.on_blip_change()

if __name__ == '__main__':
	me = robot.Robot('Sybil',
		image_url='http://sybil-labs.appspot.com/favicon.ico',
		version=os.environ['CURRENT_VERSION_ID'],
		profile_url='http://sybil-labs.appspot.com/')
	me.RegisterHandler(events.FORM_BUTTON_CLICKED, on_button_click)
	me.RegisterHandler(events.WAVELET_SELF_ADDED, on_robot_added)
	me.RegisterHandler(events.WAVELET_TITLE_CHANGED, on_title_change)
	me.RegisterHandler(events.BLIP_SUBMITTED, on_blip_change)
	me.Run()
