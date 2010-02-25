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

import  time
import  logging
import  os

from    google.appengine.api import memcache
from    google.appengine.ext import webapp

from    common      import stores, utils

from    datetime    import datetime
from    urlparse    import urlparse

# get registry, we need it to register our filter later.
register = webapp.template.create_template_register()

def _now():
    now = time.localtime()[:6]
    return datetime(*now)

def _s(i):
    return (i != 1 and 's' or '')

def get_attr(obj, attr):
    return getattr(obj, attr.lower(), '')

def filter_args(url, anti_args):
    url_tuple = urlparse(url)
    url_without_args = '%s://%s%s' % (url_tuple[0], url_tuple[1], url_tuple[2])
    # Separate arguments and filter out blanks.
    args = [x for x in url_tuple[4].split('&') if x]
    anti_args = anti_args.split(',')

    for arg in args[:]:
        # Accounts for arguments in the form of 'arg' instead of 'arg=value'
        if (('=' not in arg) and (arg in anti_args)) or (arg[:arg.find('=')] in anti_args):
            args.remove(arg)

    # Prevents ?&'s in the url
    amp = args and '&' or ''
    return '%s?%s%s' % (url_without_args, '&'.join(args), amp)

def build_date(then):
    """build_date(then: datetime.datetime) -> str

    Build a date string that changes as time goes on.
    Examples:
        Item posted
        < 5 seconds: a moment ago
        < 1 minute: 16 seconds ago
        < 1 hour: 34 minutes ago
        today: Today, 09:23
        this week: Tuesday, 11:40
        later: May 13 08

    """

    assert isinstance(then, datetime), "recieved %s instead of %s" % (type(then), datetime)

    diff = (_now() - then)
    seconds = diff.seconds
    minutes = seconds / 60
    hours = minutes / 60
    days = diff.days

    if days > 7:
        return then.strftime('%b %d, %Y, %H:%M GMT')
    if days < 1:
        if seconds < 5:
            return 'a moment ago'
        if seconds < 60:
            return '%d second%s ago' % (seconds, _s(seconds))
        if minutes < 60:
            return '%d minute%s ago' % (minutes, _s(minutes))

        return then.strftime('Today, %H:%M GMT')

    return then.strftime('%A, %H:%M GMT')

def trunc(string, n=3):
    n = int(n)
    string = str(string)
    return string[:n]+'...'+string[-n:]

class MarkupStorage(object): pass

def markup(obj, attr, nocache=False, norender=False):

    # Return the prerendered version of the attribute, if applicable.
    if norender and hasattr(obj, 'html_%s' % attr):
        value = getattr(obj, 'html_%s' % attr, '')
        if value:
            return value

    value = getattr(obj, attr, '')
    extra = getattr(obj, 'common', '')

    if not hasattr(obj, 'markup'):
        return value

    cache_key = "markup:%s" % (obj.key_name)
    result = memcache.get(cache_key) or MarkupStorage()

    if not hasattr(result, attr):
        setattr(result, attr, eval(obj.markup.lower())(value, extra))
        if not nocache:
            memcache.set(cache_key, result)

    return getattr(result, attr)

def plaintext(value, extra=''):
    return value

def textile(value, extra=''):
    try:
        import lib.textile
    except ImportError:
        return value
    else:
        # logging.info("Rendering using Textile")
        if extra:
            value = u'%s\n\r%s' % (value, extra)
        return lib.textile.textile(value, encoding='utf8', output='ascii')

def markdown(value, extra=''):
    try:
        import markdown
    except ImportError:
        return value
    else:
        if extra:
            value = '%s\n\r%s' % (value, extra)
        return markdown.markdown(value)

def rest(value, extra=''):
    try:
        from docutils.core import publish_parts
    except ImportError:
        return value
    else:
        # logging.info("Rendering using ReST")
        if extra:
            # Strip all the lines in the extra that don't begin with '..'
            #extra = '\r\n\r\n'.join([x for x in extra.rsplit('\r\n\r\n') if x and x.startswith('..')])
            value = '%s\n\r%s' % (value, extra)
        parts = publish_parts(source=value, writer_name="html4css1")
        return parts["fragment"]

def has_content(value):
    return bool([x for x in value.split('\r\n') if x and not x.startswith('..')])

def date(value, arg=''):
    "Formats a date according to the given format"
    from django.utils.dateformat import format
    if not value:
        return ''
    return format(value, arg)

def register_filters(env):
    env.filters['build_date'] = build_date
    env.filters['filter_args'] = filter_args
    env.filters['markup'] = markup
    env.filters['has_content'] = has_content
    env.filters['date'] = date
