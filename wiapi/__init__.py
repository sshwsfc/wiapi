# coding=utf-8
import cgi
import datetime
import functools
import json
import logging
import traceback
import StringIO
from UserDict import UserDict

import tornado.locale
import tornado.web
from tornado.escape import utf8
from tornado.web import HTTPError

# try:
#     import cjson
#     json.dumps = cjson.encode
#     json.loads = cjson.decode
# except Exception:
#     pass

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

class BaseApiMeta(object):
    
    def __init__(self, handler):
        self.request = handler.request
        for k,v in self.meta_map.items():
            setattr(self, k, handler.get_argument(v[1], self.request.headers.get(v[0], v[2])))

    def record(self, infos):
        for k, v in self.meta_map.items():
            p = getattr(self, k)
            if p:
                key = len(v)>3 and v[3] or v[1]
                infos[key] = p
    
    def params(self):
        return dict([(k, getattr(self, k)) for k in self.meta_map.keys()])

    def filte(self, qs):
        return qs

    @property
    def meta_map(self):
        return self.get_meta_map()

    def get_meta_map(self):
        #{ 'dpi': ('Wi-Dpi', 'dpi', '160'), }
        return {}

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


class BaseHandler(tornado.web.RequestHandler):

    def _(self, message, plural_message=None, count=None):
        if self.locale.code in self.settings.get('native_locale', []):
            return message
        return self.locale.translate(message.decode("utf-8").strip(), plural_message, count) or message

    def mail_admins(self, subject, content):
        pass

    def log_exception(self, type=None, value=None, tb=None):

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
        self.mail_admins('API ERROR: %s' % str(value), "[%s] %s" % (datetime.datetime.now(), error_info))

class ApiHandler(BaseHandler):

    # methods for extend by subclass
    def get_user(self, id_or_name, username=False):
        return None

    def get_meta_cls(self):
        return None

    def record_ex(self, infos):
        pass

    def initialize(self):
        self._bundle_buffer = {}
        #translation.activate(self.locale.code)

    def _(self, message, plural_message=None, count=None):
        if self.locale.code in self.settings.get('native_locale', []):
            return message
        return self.locale.translatstatic_urle(message.decode("utf-8").strip(), plural_message, count)

    def record(self, infos):
        if self.user:
            infos['user_id'] = str(self.user.id)
        if self.api_meta:
            self.api_meta.record(infos)
        self.record_ex(infos)

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

    def arg_dict(self):
        return dict([(k, self.arg(k)) for k in self.request.arguments.keys()])

    def static_media_url(self, url):
        return self.settings.get('static_url', '') + (url[0] == '/' and url[1:] or url)

    def file_url(self, f, tag='phone', screen_hr=False):
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
            except Exception:
                dpi = 1
            if dpi > 1:
                tag = '%dx%s' % (dpi, tag)

            if hasattr(f, 'extra_thumbnails') and f.extra_thumbnails.has_key(tag):
                    f = f.extra_thumbnails[tag]
            if hasattr(f, 'url'):
                url = f.url
            else:
                url = self.static_media_url(unicode(f))
                
            return url
        except Exception:
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
            if self.settings.get("debug", False) or self.settings.get("apidebug", False):
                test_username = self.request.headers.get('Test_user', \
                    self.request.headers.get('HTTP_TEST_USER', self.get_argument('_test_user', None)))

                if test_username:
                    return self.get_user(test_username, username=True)
                elif self.settings.get("fake_user", False):
                    return self.get_user(self.settings.get("fake_user"), username=True)
            user_id = self.get_secure_cookie("user_id")
            if user_id:
                return self.get_user(user_id)
            else:
                return None
        except Exception:
            return None

    @property
    def api_meta(self):
        if not hasattr(self, "_api_meta"):
            meta_cls = self.get_meta_cls()
            if meta_cls:
                self._api_meta = meta_cls(self)
            else:
                self._api_meta = None
        return self._api_meta

    def send_error(self, status_code=500, **kwargs):
        if 'msg' in kwargs and 'exc_info' not in kwargs:
            raise HTTPError(status_code, kwargs['msg'])
        else:
            super(ApiHandler, self).send_error(status_code, **kwargs)

    def write_error(self, status_code, **kwargs):
        result = {"code": status_code, "msg": self._reason}
        if self.settings.get("debug") and "exc_info" in kwargs:
            result['exc_info'] = ''.join(traceback.format_exception(*kwargs["exc_info"]))
        self.write(result)

    def write(self, chunk):
        _bundle = getattr(self, "_bundle", None)

        if _bundle:
            self._bundle_buffer = {self.request.path: chunk}
            return

        assert not self._finished

        if self.arg_bool('windowname'):
            html = '<html><script type="text/javascript">window.name=\'%s\';</script></html>'
            if type(chunk) in (dict, list):
                chunk = self.json_dumps(chunk)
            self._write_buffer.append(html % utf8(chunk.replace("'", "\\'").replace('\r\n', ' ')))
        else:
            if type(chunk) in (dict, list):
                chunk = self.json_dumps(chunk)
                if self.arg('cb', False):
                    chunk = '%s(%s)' % (self.arg('cb'), chunk)
                self.set_header("Content-Type", "application/json; charset=UTF-8")
                chunk = utf8(chunk)
                self._write_buffer.append(chunk)
            else:
                super(ApiHandler, self).write(chunk)

    def json_dumps(self, chunk):
        return json.dumps(chunk, ensure_ascii=False, \
            indent=self.arg_bool('json_indent') and 4 or None)

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

        if hasattr(self.api_meta, 'filte'):
            qs = self.api_meta.filte(qs)
        total_count = len(qs)

        if total_count > 0:
            if start == -1:
                import math

                start = int(math.ceil(float(total_count) / count) - 1) * count
            qs = qs[start:start + count]
            items = convert_func is None and qs or [convert_func(item, **kwargs) for item in qs]
        else:
            items = []
        return {'total_count': total_count, 'items': items}

    def static_url(self, path):
        return self.settings.get('static_url_prefix', '/static/') + path
