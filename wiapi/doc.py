from django.utils import simplejson
from wiapi import *

class ApiDocHandler(BaseHandler):
    def get(self):
        all_apis = api_manager.get_apis(name=self.get_argument('name', None), module=self.get_argument('module', None),
                                        handler=self.get_argument('handler', None))
        apis = {}
        for api in all_apis:
            if not apis.has_key(api.module):
                apis[api.module] = []
            apis[api.module].append(api)
        
        App = type('App', (object,), {'name': "7game",})
        app = App()

        self.render('api_docs.html', **{'apis': apis, 'api_base': self.settings.get("api_base", ''),\
                                        'test_app_key': "", 'test_app': app,
                                        'test_user_name': self.settings.get("test_user_name", '')})


class ApiMapHandler(BaseHandler):
    def get(self):
        all_apis = api_manager.get_apis(name=self.get_argument('name', None), module=self.get_argument('module', None),
                                        handler=self.get_argument('handler', None))
        apis = {}
        for api in all_apis:
            if not apis.has_key(api.module):
                apis[api.module] = []
            apis[api.module].append(api)
        self.render('api_map.html', **{'apis': apis, 'api_base': self.settings.get("api_base", ''), })


class ApiAppKeyHandler(BaseHandler):
    def get(self):
        app_keys = {}
        self.write(simplejson.dumps(app_keys))


class ApiExampleHandler(ApiHandler):
    def get(self):
        id = self.get_argument('id')
        parts = id.split('.')
        data = {'ex': TestDatas(self.app, self.user)}
        try:
            for p in parts:
                data = (type(data) is dict) and data[p] or getattr(data, p)
        except Exception:
            data = ''
        if hasattr(data, 'val'):
            v = data.val()
        else:
            v = data
        if type(v) in (list, tuple, dict):
            if v:
                self.write(simplejson.dumps(v))
            else:
                self.write('null')
        else:
            self.write(v)
