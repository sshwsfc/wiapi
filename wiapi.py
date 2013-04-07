# coding=utf-8

import tornado.web
import tornado.locale
from tornado.web import HTTPError

import hashlib, cgi
#from utils import *
#from meta import ApiMeta

import re
import os
import tempfile
import datetime
import decimal
import functools
import logging
from UserDict import UserDict

#from django.db.models.query import QuerySet
#from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

#from django.core.cache import cache
#from django.core.files.uploadedfile import TemporaryUploadedFile, InMemoryUploadedFile
from tornado.escape import utf8, _unicode
import views

class objid(str):
    pass

class dbid(str):
    pass

try:
    import cjson as json

    json.dumps = cjson.encode
    json.loads = cjson.decode
except Exception, e:
    import json

def truncate_zh(value, number=9):
    """
     Truncate a string including chinese characters.
     Argument:Numbers of characters to truncate after.
     """
    try:
        char_len = len(value)
        if int(number) < char_len:
            return value[0:int(number)] + '...'
        else:
            return value
    except:
        return value


class ExampleParam(dict):
    def __init__(self, parent, name):
        self['_parent'] = parent
        self['_name'] = name

    def __getattr__(self, name):
        if not self.has_key(name):
            self[name] = ExampleParam(self, name)
        return self[name]

    def __str__(self):
        if self['_parent']:
            return '%s.%s' % (self['_parent'], self['_name'])
        else:
            return self['_name']

    def print_tree(self, pre=''):
        ps = ['%s%s%s' % (pre, k, (lambda vp: vp and ':\r\n%s' % vp or '')(v.print_tree(pre + '\t'))) for k, v in
              self.items() if k not in ('_parent', '_name')]
        if ps:
            return "%s" % '\r\n'.join(ps)
        else:
            return ""

ex = ExampleParam({}, 'ex')

class ApiDefined(UserDict):
    def __init__(self, name, method, uri, params=[], result=None, need_login=False, need_appkey=False, handler=None,
                 module=None, filters=[], description=''):
        UserDict.__init__(self)
        self['name'] = name
        self['method'] = method
        self['module'] = module
        self['uri'] = uri
        self['handler'] = handler
        self['params'] = params
        self['result'] = result
        self['need_login'] = need_login
        self['need_appkey'] = need_appkey
        self['filters'] = filters
        self['description'] = description

    def get_handler_name(self):
        return self['handler'].__name__

    def doc(self):
        d = '%s\n%s %s' % (self['name'], self['method'], self['uri'])
        d = d + '\nname\trequired\ttype\tdefault\texample\t\tdesc'
        d = d + '\n------------------------------------------------'
        for p in self['params']:
            d = d + '\n%s\t%s\t%s\t%s\t%s\t%s' % (
                p.name, p.required, p.param_type.__name__, p.default, p.display_example(), p.description)
        if self['result']:
            d = d + '\nResult:\n%s' % self['result']
        return d

    def __getattr__(self, name):
        try:
            return self[name]
        except Exception:
            return None


class Param(UserDict):
    def __init__(self, name, required=False, param_type=str, default=None, example=None, description="", hidden=False):
        UserDict.__init__(self)
        self['name'] = name
        self['required'] = required
        self['param_type'] = param_type
        self['default'] = default
        self['example'] = example
        self['description'] = description
        self['hidden'] = hidden

    def display_type(self, _t=None):
        _t = _t or self['param_type']
        if type(_t) in (list, tuple) and _t:
            return '[%s,..]' % self.display_type(_t[0])
        return _t.__name__

    def display_example(self):
        if self['hidden']: return ''
        if self['param_type'] is bool:
            return self['example'] and 'true' or 'false'
        else:
            return str(self['example'])

    def html_example(self):
        if self['hidden']: return ''
        if type(self['example']) is ExampleParam:
            return '<input type="text" class="example_input" name="%s" value=""><a class="example_value" val="%s">E</a>'\
            % (self['name'], str(self['example']))
        if self['param_type'] is file:
            return '<input name="%s" type="file"/>' % self['name']
        if self['param_type'] is bool:
            return '<select name="%s"><option value="true"%s>True</option><option value="false"%s>False</option></select>' %\
                   (self['name'], self['example'] and ' selected' or '', (not self['example']) and ' selected' or '')
        elif self['param_type'] in (str, int, float):
            if type(self['example']) in (list, tuple):
                return '<select name="%s">%s</select>' % (
                    self['name'], ''.join(['<option value="%s">%s</option>' % (v, v) for v in self['example']]))
        return '<input type="text" name="%s" value="%s">' % (self['name'], str(self['example']))

    def __getattr__(self, name):
        try:
            return self[name]
        except Exception:
            return None


class ApiHolder(object):
    apis = []

    def __init__(self):
        pass

    def addapi(self, api):
        api['id'] = len(self.apis) + 1
        self.apis.append(api)

    def get_apis(self, name=None, module=None, handler=None):
        all_apis = self.apis
        if name:
            name = name.replace(' ', '_').lower()
            all_apis = filter(lambda api: api.name.lower().replace(' ', '_') == name, all_apis)
        if module:
            all_apis = filter(lambda api: api['module'] == module, all_apis)
        if handler:
            handler = handler.lower()
            all_apis = filter(lambda api: api['handler'].__name__.lower() == handler or api[
                                                                                        'handler'].__name__.lower() == '%shandler' % handler
                              , all_apis)
        return all_apis

    def get_urls(self):
        urls = {}
        for api in self.apis:
            if not urls.has_key(api['uri']):
                urls[api['uri']] = api['handler']
        return [(r'%s$' % uri, handler) for uri, handler in urls.items()]

api_manager = ApiHolder()

def api(name, uri, params=[], result=None, filters=[], description=''):
    def wrap(method):
        if not hasattr(method, 'apis'):
            setattr(method, 'apis', [])
        getattr(method, 'apis').append(
            ApiDefined(name, method.__name__.upper(), uri, params, result, module=method.__module__, filters=filters,
                       description=description))
        return method

    return wrap


def handler(cls):
    for m in [getattr(cls, i) for i in dir(cls) if callable(getattr(cls, i)) and hasattr(getattr(cls, i), 'apis')]:
        method_filters = getattr(m, 'api_filters', None)
        for api in m.apis:
            api['handler'] = cls
            if method_filters:
                for f in method_filters:
                    f(api)
            if api['filters']:
                for f in api['filters']:
                    f(api)
            api_manager.addapi(api)
    return cls


def ps_filter(api):
    api.params.extend(
        [Param('start', False, int, 0, 0, 'Data Start'), Param('count', False, int, 25, 25, 'Data Count')])

def app_required(method=None, cross_app=False):
    def appkey_filter(api):
        api['need_appkey'] = True

    if method:
        api_filters = getattr(method, 'api_filters', [])
        api_filters.append(appkey_filter)
        setattr(method, 'api_filters', api_filters)

        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            if not self.app:
                raise HTTPError(403)

            if self.request.method != 'GET' and hasattr(self, 'cross_app'):
                raise HTTPError(403)

            return method(self, *args, **kwargs)

        return wrapper
    else:
        def app_required_wrap(_method):
            api_filters = getattr(_method, 'api_filters', [])
            api_filters.append(appkey_filter)
            setattr(_method, 'api_filters', api_filters)

            @functools.wraps(_method)
            def wrapper(self, *args, **kwargs):
                if not self.app:
                    raise HTTPError(403)

                if not cross_app and hasattr(self, 'cross_app'):
                    raise HTTPError(403)

                return _method(self, *args, **kwargs)

            return wrapper

        return app_required_wrap


def auth_required(method):
    def auth_filter(api):
        api['need_login'] = True

    api_filters = getattr(method, 'api_filters', [])
    api_filters.append(auth_filter)
    setattr(method, 'api_filters', api_filters)

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.current_user:
            raise HTTPError(401)
        return method(self, *args, **kwargs)

    return wrapper


class BaseHandler(views.BaseHandler):
    def _(self, message, plural_message=None, count=None):
        if self.locale.code in self.settings.get('native_locale', []):
            return message
        return self.locale.translate(message.decode("utf-8").strip(), plural_message, count) or message


    def log_exception(self, type=None, value=None, tb=None):
        import traceback
        import StringIO

        exce_info = StringIO.StringIO()
        exc_info = True
        if type and value and tb:
            traceback.print_exception(type, value, tb, 10, exce_info)
        else:
            exc_info = False
            traceback.print_exc(10, exce_info)

        error_info = "%s\n========= EXCEPTION INFO =============\n%s\n========= HTTP REQUEST INFO ==========\n%s" %\
                     (self._request_summary(), exce_info.getvalue(), self.request)

        logging.error(error_info, exc_info=exc_info)
        mail_admins('API ERROR: %s' % str(value), "[%s] %s" % (datetime.datetime.now(), error_info), fail_silently=True)


    def _stack_context_handle_exception(self, type, value, tb):
        _bundle = getattr(self, "_bundle", None)
        if _bundle:
            return

        if isinstance(value, ObjectDoesNotExist):
            self.send_error(400, exception=value)
        elif isinstance(value, MultipleObjectsReturned):
            self.send_error(400, exception=value)
            self.send_error(400, exception=value)
        elif isinstance(value, HTTPError):
            self._handle_request_exception(value)
        else:
            self.log_exception(type, value, tb)
            self.send_error(500, exception=value)
        return True
class MultipartPatchMix(object):
    pass
class ApiHandler(MultipartPatchMix, BaseHandler):
    def initialize(self):
        self._bundle_buffer = {}
        translation.activate(self.locale.code)
        super(MultipartPatchMix, self).initialize()

    def _(self, message, plural_message=None, count=None):
        if self.locale.code in self.settings.get('native_locale', []):
            return message
        return self.locale.translatstatic_urle(message.decode("utf-8").strip(), plural_message, count)

    def record(self, infos):
        if self.app:
            infos['app_id'] = str(self.app.id)
        if self.user:
            infos['user_id'] = str(self.user.id)
        self.api_meta.record(infos)
        self.record_ex(infos)

    def record_ex(self, infos):
        pass
        # if self.user:
        #     wibox_home = self.user.userinfo.wibox_home
        #     if wibox_home:
        #         infos['ex_ab'] = wibox_home

    def get_browser_locale(self, default="en_US"):
        """Determines the user's locale from Accept-Language header.
          See http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.4
          """

        if "Accept-Language" in self.request.headers:
            languages = self.request.headers["Accept-Language"].split(",")
            locales = []
            for language in languages:
                parts = language.strip().split(";")
                if len(parts) > 1 and parts[1].startswith("q="):
                    try:
                        score = float(parts[1][2:])
                    except (ValueError, TypeError):
                        score = 0.0
                else:
                    score = 1.0
                locales.append((parts[0], score))
            if locales:
                locales.sort(key=lambda (l, s): s, reverse=True)
                codes = [(l[0].lower() == 'zh' and 'zh_CN' or l[0]) for l in locales]
                return tornado.locale.get(*codes)
        return tornado.locale.get(default)

    def auth_login(self, user):
        self.user_key = self.create_signed_value("user_id", str(user.id))
        self.set_cookie("user_id", self.user_key, expires_days=3650)
        #self.set_cookie("uid", str(user.id), expires_days=100)
        if user.is_guest:
            self.set_cookie("guest", 'true', expires_days=1)
        user.last_login = datetime.datetime.now()
        user.save()
        self._current_user = user

    def auth_logout(self):
        self.clear_cookie("user_id")
        self._current_user = None

    def has_arg(self, name):
        return self.request.arguments.has_key(name)

    def arg(self, name, default=tornado.web.RequestHandler._ARG_DEFAULT, strip=True):
        return self.get_argument(name, default, strip)

    def arg_escape(self, name, default=tornado.web.RequestHandler._ARG_DEFAULT, strip=True):
        return cgi.escape(self.arg(name, default, strip))

    def arg_bool(self, name):
        return self.arg(name, 'false') == 'true'

    def args(self, name, default=[], separator=','):
        value = self.get_argument(name, None)
        if value:
            return value.split(',')
        else:
            return default

    def static_media_url(self, url):
        return self.settings.get('static_url', '') + (url[0] == '/' and url[1:] or url)

    def file_url(self, f, tag='phone', screen_hr=False,rotate=-90):
        if f is None:
            return ''

        if screen_hr:
            tag += "_hr"

        #if f is url
        if type(f) in (str, unicode):
            if f.startswith('http://'):
                return unicode(f)
            else:
                return self.static_media_url(unicode(f))

        try:
            try:
                dpi = int(self.api_meta.highdpi)
            except Exception, e:
                dpi = 1
            if dpi > 1:
                tag = '%dx%s' % (dpi, tag)

            key = '%s:%s:%s' % ('img', f.url, tag)
            url = cache.get(key)
            if url is not None:
                return url

#            if screen_hr:
#                setattr(f,"rotate",rotate)
            
            if hasattr(f, 'extra_thumbnails') and f.extra_thumbnails.has_key(tag):
                    f = f.extra_thumbnails[tag]
            if hasattr(f, 'url'):
                url = f.url
            else:
                url = self.static_media_url(unicode(f))
                
            cache.set(key, url, 100 * 60)
            return url
        except Exception, e:
            return ''

    def blob_url(self, obj, field='blob'):
        current_site = self.settings.get('api_base').replace('https', 'http')
        blob_url = u"%s%s" % (
            unicode(current_site),
            '/blob/%s/%s/%s' % (obj.__class__.__name__.lower(), str(obj.id), field),
            )
        return blob_url


    @property
    def current_site(self):
        return self.settings.get('api_base').replace('https', 'http')

    def prepare(self):
        if self.user:
            ping_user_online(self.user)


    def is_mobile(self, mobile):
        mobile_start = ['130', '131', '132', '133', '134', '135', '136', '137', '138', '139', '147', '150', '151',\
                        '152', '153', '155', '156', '157', '158', '159', '186', '187', '188']

        for m in mobile_start:
            if mobile.startswith(m):
                return True

        return False
    def get_cookie(self, name, default=None):
        if name == 'user_id' and self.has_arg('session_key'):
            return self.arg('session_key')
        return super(ApiHandler, self).get_cookie(name, default)

    @property
    def user(self):
        return self.current_user

    @property
    def current_user(self):
        if not hasattr(self, "_current_user"):
            user = self.get_current_user()
            if user:
                setattr(self, "_current_user", user)
        return getattr(self, "_current_user", None)

    def get_current_user(self):
        try:
        # debug
            if self.settings.get("debug", False) or self.settings.get("apidebug", False):
                test_username = self.request.headers.get('Test_user', self.request.headers.get('HTTP_TEST_USER',
                                                                                               self.get_argument(
                                                                                                   '_test_user', None)))

                if test_username:
                    return User.get(test_username, username=True)
                elif self.settings.get("fake_user", False):
                    return User.get(self.settings.get("fake_user"), username=True)
            user_id = self.get_secure_cookie("user_id")
            if user_id:
                #return User.objects.get(id=user_id)
                user = User.get(user_id)
                return user
            else:
                return None

        except Exception, e:
            return None

    @property
    def app(self):
        pass


    def get_current_app(self):
        pass

    @property
    def api_meta(self):
        if not hasattr(self, "_api_meta"):
            self._api_meta = ApiMeta(self)
        return self._api_meta

    @property
    def pcode(self):
        return str(platform_id(self.api_meta.platform_code))

    def send_error(self, status_code=403, **kwargs):
        _bundle = getattr(self, "_bundle", None)

        if _bundle:
            log_message = kwargs.get('msg') or kwargs.get('exception')
            raise HTTPError(status_code, log_message=log_message)

        if self._headers_written:
            logging.error("Cannot send error response after headers written")
            if not self._finished:
                self.finish()
            return
        self.clear()
        self.set_status(status_code)

        if status_code < 500:
            if kwargs.has_key('exception') and not kwargs.has_key('msg'):
                kwargs['msg'] = str(kwargs['exception'])
                del kwargs['exception']
            # if self.api_meta.sdk_version >= '3.0' or not kwargs.has_key('msg'):
                # self.write(kwargs)
            # else:
            self.write(kwargs)

        if not self._finished and not _bundle:
            self.finish()

    def write(self, chunk):
        _bundle = getattr(self, "_bundle", None)

        if _bundle:
            self._bundle_buffer = {self.request.path: chunk}
            return

        assert not self._finished
        if type(chunk) in (QuerySet,):
            chunk = self.ps(chunk)

        if self.arg_bool('windowname'):
            html = '<html><script type="text/javascript">window.name=\'%s\';</script></html>'
            if type(chunk) in (dict, list):
                chunk = simplejson.dumps(chunk, cls=ApiJSONEncoder, ensure_ascii=False)
            self._write_buffer.append(html % utf8(chunk.replace("'", "\\'").replace('\r\n', ' ')))
        else:
            if type(chunk) in (dict, list):
                chunk = simplejson.dumps(chunk, cls=ApiJSONEncoder, ensure_ascii=False,
                                         indent=self.arg_bool('json_indent') and 4 or None)
                if self.arg('cb', False):
                    chunk = '%s(%s)' % (self.arg('cb'), chunk)
                self.set_header("Content-Type", "application/json; charset=UTF-8")
                chunk = utf8(chunk)
                self._write_buffer.append(chunk)
            else:
                super(ApiHandler, self).write(chunk)


    def get_page(self):
        start = int(self.get_argument('start', 0))
        count = int(self.get_argument('count', 12))
        return {"start": start, "count": count}

    def gen_list_out(self, items, total_count):
        return {'total_count': total_count, 'items': items}

    def ps(self, qs, convert_func=None, **kwargs):
        start = int(self.get_argument('start', 0))
        count = int(self.get_argument('count', 25))

        if(start < 0 or count > 100 or count < 0):
            raise Exception(u"分页参数错误")

        if (type(qs) in (list, set)):
            total_count = len(qs)
        else:
            qs = self.api_meta.filte(qs)
            total_count = qs.count()
            if type(qs) not in (QuerySet,):
                qs = qs.all()

        if total_count > 0:
            if start == -1:
                import math

                start = int(math.ceil(float(total_count) / count) - 1) * count
            qs = qs[start:start + count]
            items = convert_func is None and qs or [convert_func(item, **kwargs) for item in qs]
        else:
            items = []
        return {'total_count': total_count, 'items': items}

    def get_uploadfile(self, name):
        if self.request.files.has_key(name):
            file_obj = self.request.files[name][0]
            body = file_obj['body']
            f = TemporaryUploadedFile(file_obj['filename'], file_obj['content_type'], 0, None)
            f.write(body)
            f.seek(0)
            f.size = len(body)
            return f
        else:
            return None

    def static_url(self, path):
        return self.settings.get('static_url_prefix', '/static/') + path
