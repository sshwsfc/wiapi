# -*- coding: utf-8 -*- 
import logging
import os.path
from logging.handlers import TimedRotatingFileHandler
import shutil, zlib
from datetime import datetime

def api_log_function(h):
    if h.get_status() < 400 and h.request.method != "GET1":
        loginfo = '[%s] %s %s %s' % (
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'), h.request.remote_ip, h.request.method, h.request.path)
        infos = dict([(ak, av[-1]) for ak, av in h.request.arguments.items() if\
                                   ak not in ('app_key', 'sig', 'session_key') and not ak.startswith('im_')])
        if hasattr(h, 'record'):
            h.record(infos)

        try:
            if settings.DEBUG:
                print loginfo + "?" + '&'.join(['%s=%s' % (k, unicode(v, 'utf8')) for k, v in infos.items()])

            ubelogger.log(loginfo + "?" + '&'.join(['%s=%s' % (k, unicode(v, 'utf8')) for k, v in infos.items()]))
        except Exception, e:
            print e
            ubelogger.log(loginfo + "?" + '&'.join(['%s=%s' % (k, v) for k, v in infos.items()]))
