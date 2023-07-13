#!/usr/bin/env python
# coding=utf-8
'''
Author: ChenHaonan
Date: 2023-07-14 01:59:25
LastEditors: ChenHaonan
LastEditTime: 2023-07-14 02:07:42
Description: 
'''

import os
from tsi_server import ServerMsgDir,Config
from supermind.api import upload_file

class MindGoTrader(ServerMsgDir):

    def order(self,symbol,volume,price):
        '''
        下单接口,对接supermind远程文件单
        '''
        signal = self.gen_signal('order',symbol,volume,price)
        self.dump_local_signals(signal)
        res = upload_file(
             file = os.path.join(self.conf.PATH_ORDER,signal),
             path = self.conf.PATH_ORDER_SUPERMIND
        )
        return res
            
    
    def cancel_order(self,order_ids):
        signal = self.gen_signal('cancel',order_ids)
        self.dump_local_signals(signal)
        res = upload_file(
             file = os.path.join(self.conf.PATH_ORDER,signal),
             path = self.conf.PATH_ORDER_SUPERMIND
        )
        return res
    
if __name__ == '__main__':
    path_order = r'C:/Users/chenhaonan/_supermind_/path_order/' # 自行替换成本机文件单储存路径,否则报错
    path_order_supermind = './path_order/' # 自行替换成supermind云端文件单储存路径，否则报错
    conf = Config(PATH_ORDER = path_order,PATH_ORDER_SUPERMIND=path_order_supermind)
    atrader = MindGoTrader(conf)
    atrader.order('000001.SZ',100,15.11)
    atrader.cancel_order(['544957'])