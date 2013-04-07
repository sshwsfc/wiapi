# -*- coding: utf-8 -*- 
import logging
from datetime import datetime

def api_log_function(application, h):
    if h.get_status() < 400:
        loginfo = '[%s] %s %s %s' % (
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'), h.request.remote_ip, h.request.method, h.request.path)
        infos = dict([(ak, av[-1]) for ak, av in h.request.arguments.items() if\
                                   ak not in ('app_key', 'sig', 'session_key') and not ak.startswith('im_')])
        if hasattr(h, 'record'):
            h.record(infos)

        if application.settings.get('debug', False):
            print loginfo + "?" + '&'.join(['%s=%s' % (k, unicode(v, 'utf8')) for k, v in infos.items()])
        else:
            logging.info(loginfo + "?" + '&'.join(['%s=%s' % (k, unicode(v, 'utf8')) for k, v in infos.items()]))
