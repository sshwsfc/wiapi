# coding=utf-8
import tornado.web
import tornado.locale
import os
import csv
import codecs
import logging

cache = {}
jsi18n_cache = {}

class BaseHandler(tornado.web.RequestHandler):
            
    def _(self, message, plural_message=None, count=None):
        if self.locale.code in self.settings.get('native_locale', []):
            return message
        return self.locale.translate(message.decode("utf-8").strip(), plural_message, count) or message
            
    # def get_user_locale(self):
    #   return tornado.locale.get('en_US')

class ContentHandler(BaseHandler):
    
    def get_html_string(self, path, context):
        if path == 'wibox/submenu/js':
            try:
                return self.render_string('wibox/submenu.js', **context)
            except Exception, err:
                raise tornado.web.HTTPError(404)
        try:
            return self.render_string(path+ ".html", **context)
        except Exception, err:
            logging.error(err)
            raise tornado.web.HTTPError(404)
    
    def get(self, path='dashboard'):
        if path == '':
            path = 'dashboard'
        path  = path.replace('.', '/')
                    
        is_highdpi = False
        if self.get_cookie('wigame_config_highdpi', '1') == '2':
            is_highdpi = True
            
        settings = self.application.settings
        server_area = settings.get('server_area', 'china')
            
        key = ':'.join((path, self.locale.code, server_area, str(is_highdpi)))
        context = {'is_highdpi':is_highdpi, 'settings':settings, 'server_area': server_area, \
            'debug':settings.get('debug'), 'lang': self.locale.code, '_':self._}
        
        if not self.application.settings.get('debug', False):
            if not cache.has_key(key):
                cache[key] = self.get_html_string(path, context)
            self.finish(cache.get(key))
        else:
            self.finish(self.get_html_string(path, context))
        
    def static_url(self, path):
        return self.settings.get('static_url_prefix', '/static/') + path

class JS18nHandler(BaseHandler):
    
    def get_user_locale(self):
        code = self.get_argument('locale', None)
        if code:
            return tornado.locale.get(code)
        else:
            return None
    
    def _get_local_file(self):
        local_root = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'locale/translates')
        return os.path.join(local_root, '%s.csv' % self.locale.code)
    
    def _get_words(self):
        result = []
        desc = None
        try:
            f = open(self._get_local_file(), 'r')
        except:
            return result
        for i, row in enumerate(csv.reader(f)):
            if not row or len(row) < 2:
                if len(row) == 1 and row[0].startswith('#'):
                    desc = row[0][1:].strip()
                continue
            if desc == ':js':
                key, translation = row[:2]
                word = [key, translation]
                result.append(word)
        f.close()
        return result
        
    def _get_content(self):
        words = []
        if self.locale.code not in self.settings.get('native_locale', []):
            words = self._get_words()
        return self.render_string("i18n.js", words=words)
    
    def get(self):
        key = self.locale.code
        self.set_header("Content-Type", "text/javascript; charset=UTF-8")
        if not self.application.settings.get('debug', False):
            if not jsi18n_cache.has_key(key):
                jsi18n_cache[key] = self._get_content()
            self.finish(jsi18n_cache.get(key))
        else:
            self.finish(self._get_content())

class TranslateHandler(tornado.web.RequestHandler):
    
    def _get_local_file(self):
        local_root = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'locale/translates')
        return os.path.join(local_root, 'en_US.csv')
    
    def _get_words(self):
        f = open(self._get_local_file(), 'r')
        result = []
        m = {}
        s = self.get_argument('s', 'all')
        desc = []
        for i, row in enumerate(csv.reader(f)):
            if not row or len(row) < 2:
                if len(row) == 1 and row[0].startswith('#'):
                    desc.append(row[0][1:].strip())
                continue
            key, translation = row[:2]
            if s == 'all' or (s == 'untrans' and translation == "") or (s == 'trans' and translation != ""):
                id = 'w_%s' % key.__hash__()
                if not m.has_key(id):
                    m[id] = key
                    word = [id, key, translation, desc]
                    result.append(word)
            if len(desc): desc = []
        f.close()
        return result, m
        
    def _write_words(self, words):
        f = codecs.open(self._get_local_file(), 'w', 'utf-8')
        for w in words:
            if w[3]:
                f.write(u'\n')
                for d in w[3]:
                    f.write(u'# %s\n' % d.decode('utf-8'))
            f.write((u'"%s","%s"\n' % (w[1].decode('utf-8'), w[2].decode('utf-8'))))
        f.flush()
        f.close()
    
    def get(self):
        words, m = self._get_words()
        self.finish(self.render_string("translate.html", words=words, s=self.get_argument('s', 'all')))
        
    def post(self):
        cw = {}
        for key in self.request.arguments.keys():
            if key.startswith('w_'):
                cw[key] = self.get_argument(key)
        words, m = self._get_words()
        for w in words:
            if cw.has_key(w[0]):
                w[2] = cw[w[0]]
        self._write_words(words)
        tornado.locale.load_translations(os.path.join(os.path.dirname(__file__), "locale/translates"))
        