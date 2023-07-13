#!/usr/bin/env python
# coding=utf-8
'''
Author: ChenHaonan
Date: 2023-07-14 01:59:16
LastEditors: ChenHaonan
LastEditTime: 2023-07-14 02:08:48
Description: 
'''

from tsi_server import ServerExec,Config
from tick_trade_api import TradeAPI

class ServerExecMindgo(ServerExec):
    def __init__(self,conf,trade_api):
        super(ServerExec,self).__init__(conf)
        self.trade_api = trade_api
    
    def exec(self):
        cmds = self.load_local_cmds()
        for cmd in cmds:
            if cmd[1][0] == 'order':
                self.exec_order(cmd[1])
            elif cmd[1][0] == 'cancel':
                self.exec_cancel(cmd[1])
        return cmds

    def exec_order(self, cmd):
        '''
        执行订单
        '''
        if cmd[0] != 'order':
            return
        symbol, volume, price = cmd[1]
        order_id = self.trade_api.order(symbol, volume, float(price))
        return order_id

    def exec_cancel(self, cmd):
        '''
        执行撤单
        '''
        if cmd[0] != 'cancel':
            return
        order_ids = cmd[1]
        for order_id in order_ids:
            try:
                b = self.trade_api.cancel_order(order_id)
            except:
                print('error')
                
if __name__ == '__main__':
    path_order = './path_order/' #自行替换成云端文件单储存路径
    path_order_backup = './path_order_backup/' #自行替换成云端文件单(已执行的)储存路径
    trade_api = TradeAPI('84728197') #替换资金账号
    conf = Config(PATH_ORDER = path_order,PATH_ORDER_BACKUP=path_order_backup)
    clerk = ServerExecMindgo(conf,trade_api)
    import time
    
    while True:
        clerk.exec()
        time.sleep(0.01)
        break