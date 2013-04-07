#!/usr/bin/env python
import os, sys
import os.path

import tornado.auth
import tornado.httpserver
import tornado.ioloop
import tornado.web
from tornado.options import options, define, parse_command_line

from logger import api_log_function
from wiapi import api_manager

PROJECT_ROOT = os.path.realpath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, os.pardir))

app_settings = {
    "api_prefix": "",
    "api_base": 'http://127.0.0.1:9000',
    'cookie_secret': 'de2f899661fc8199f0d914abf1c21217',
    "xsrf_cookies": False,
    'native_locale': ['zh', 'zh_CN'],
    "debug": True,
    "apidebug": True,
    "autoescape": None,
    "record_ube": True,
    "apis": [],
}
try:
    from my_settings import load_api_settings
    load_api_settings(app_settings)
except:
    pass

for api_module in app_settings['apis']:
    __import__(api_module)
    
apiurls = api_manager.get_urls()

#rest set
resturls = []
for uri in apiurls:
    ruri = uri[0]
    name =  uri[1].__module__
    ruri = ruri.replace(":id","([\w\d]+)?")
    resturls.append((ruri,uri[1],))
apiurls = resturls

#setup docs
if app_settings.get('apidebug', False):
    import doc

    apiurls = apiurls + [
            (r"/doc$", doc.ApiDocHandler),
            (r"/doc/apps$", doc.ApiAppKeyHandler),
            (r"/doc/example$", doc.ApiExampleHandler),
            (r"/map$", doc.ApiMapHandler),
    ]
    app_settings.update({
        "template_path": os.path.join(PROJECT_ROOT, "docs"),
        "static_path": os.path.join(PROJECT_ROOT, "docs"),
        "static_url_prefix": '%s/doc/static/' % app_settings.get('api_prefix', ''),
        })

handlers = [(app_settings.get('api_prefix', '') + u[0], u[1]) for u in apiurls]

class MyApplication(tornado.web.Application):

    def log_request(self, handler):
        if self.settings.get("record_ube", True):
            api_log_function(self, handler)

application = MyApplication(handlers, **app_settings)
define('port', type=int, default=80)

def main():
    parse_command_line()
    http_server = tornado.httpserver.HTTPServer(application, no_keep_alive=True, xheaders=True)
    http_server.bind(options.port)
    if application.settings.get("debug"):
        http_server.start()
    else:
        http_server.start()
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()

