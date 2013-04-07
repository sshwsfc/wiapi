# coding=utf-8
from wiapi import handler, ApiHandler, api, Param

@handler
class GameHandler(ApiHandler):
    @api('Game Info', '/game', [
        Param('game_id', True, int, None, 10, '应用id'),
        Param('web', False, bool, None, False, '是否为网页调用'),
        ], description="返回应用信息")
    def get(self):
        self.write({'name': 'hello world, 你好世界'})