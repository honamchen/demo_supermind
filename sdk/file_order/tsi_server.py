#!/usr/bin/env python
# coding=utf-8
'''
Author: ChenHaonan
Date: 2023-07-14 01:58:55
LastEditors: ChenHaonan
LastEditTime: 2023-07-14 02:09:43
Description: 
'''

import os
import shutil
import random
import numpy as np
from datetime import datetime as dt

class Config(object):
    def __init__(self, **kwargs):
        for k in kwargs:
            setattr(self, k.upper(), kwargs[k])
        p = getattr(self,'PATH_ORDER',None)
        pb = getattr(self,'PATH_ORDER_BACKUP',None)
        if p is not None and pb is None:
            pb = p+'#'+dt.now().strftime('%Y%m%d')
            setattr(self,'PATH_ORDER_BACKUP',pb)

class _Server_(object):
    def __init__(self, conf):
        self.conf = conf

    def _num_to_str_(self, num):
        if isinstance(num, float):
            s = '%.8f' % num
            while s.endswith('00'):
                s = s[:-1]

            if '.' in s and s[-1] == '0' and \
                    not s.endswith('.0'):
                s = s[:-1]
        else:
            s = str(num)
        return s

    def _random_uid_(self, length=12):
        '''
        生成随机字符串
        '''
        letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        digits = '0123456789'
        tag = getattr(self.conf,'TAG','TAG')
        return tag+'#'+''.join(random.sample(letters + digits, length))

class ServerMsg(_Server_):
    def parse_signal(self, signal):
        '''
        将本地信号解译成指令cmd@msg@others
        '''
        parts = signal.split('@')
        if len(parts) < 2:
            return None

        cmd, odr = parts[:2]
        if len(parts) > 2:
            msg = parts[2]
        else:
            msg = ''

        if cmd == 'order':
            ss = odr.split('#')
            symbol = ss[0]
            vol = int(ss[1])
            price = ss[2] if len(ss) >= 3 else None
            odr = (symbol, vol, price)
        elif cmd == 'cancel':
            odr = odr.split(',')
        return cmd, odr, msg

    def gen_signal(self, cmd, *args):
        '''
        根据指令生成信号
        '''
        if cmd == 'order':
            symbol = args[0]
            vol = args[1]
            if len(args) >= 3:
                price = args[2]
                signal = 'order@%s#%d#%s' % (
                    symbol, vol,
                    self._num_to_str_(price)
                )
            else:
                signal = 'order@%s#%d' % (symbol, vol)
            signal = signal+'@'+self._random_uid_()
            return signal
        if cmd == 'cancel':
            if len(args) == 0:
                return
            ids = args[0]
            if not isinstance(ids, list):
                ids = [ids]
            if len(ids) == 0:
                return
            ids = ','.join(ids)
            signal = '%s@%s@%s' % (
                'cancel', ids, self._random_uid_()
            )
            return signal

    def load_local_signals(self):
        '''
        从本地交互文件或目录中获取信号
        '''
        raise(NotImplementedError)

    def dump_local_signals(self, signals):
        '''
        将信号保存到交互文件或目录中
        '''
        raise(NotImplementedError)

    def load_local_cmds(self):
        '''
        从本地交互文件或目录中获取指令
        '''
        signals = self.load_local_signals()
        cmds = [(s,self.parse_signal(s)) for s in signals]
        cmds = [(c[0],c[1]) for c in cmds if c[1] is not None]
        return cmds

    def dump_local_cmds(self, cmds):
        '''
        将指令保存到交互文件或目录中
        '''
        signals = [self.gen_signal(*c) for c in cmds]
        self.dump_local_signals(signals)

class ServerMsgDir(ServerMsg):
    '''
    指定文件夹，将文件夹下的每个文件作为信号
    '''
    def _get_dirs_and_files_(self, path, full_path=False):
        '''
        获取目录下的文件夹和文件
        '''
        
        f = []
        for (dirpath, dirnames, filenames) in os.walk(path, topdown=True):
            if full_path:
                dirnames = [os.path.join(path, s) for s in dirnames]
                filenames = [os.path.join(path, s) for s in filenames]
            return dirnames, filenames

    def load_local_signals(self):
        for (dirpath, dirnames, filenames) in os.walk(
                self.conf.PATH_ORDER, topdown=True):
            # 读取信号
            signals =  filenames
            # 清空/备份信号
            for signal in signals:
                src = os.path.join(self.conf.PATH_ORDER, signal)
                prefix = dt.now().strftime('%Y%m%d%H%M%S.%f@')
                dst = os.path.join(
                    self.conf.PATH_ORDER_BACKUP,
                    prefix+signal
                )
                shutil.move(src, dst)
            return signals
        return []

    def dump_local_signals(self, signals):
        if isinstance(signals,str):
            signals = [signals]
        PATH_ORDER = self.conf.PATH_ORDER
        for signal in signals:
            meta = dt.now().strftime('%Y%m%d%H%M%S.%f@')+signal
            with open(os.path.join(PATH_ORDER, signal), 'w') as fout:
                fout.write(meta)
                
class ServerExec(ServerMsgDir):
    def exec(self):
        cmds = self.load_local_cmds()
        for cmd in cmds:
            if cmd[1][0] == 'order':
                self.exec_order(cmd)
            elif cmd[1][0] == 'cancel':
                self.exec_cancel(cmd)
        return cmds

    def exec_order(self, cmd):
        '''
        执行订单
        '''
        raise(NotImplementedError)

    def exec_cancel(self, cmd):
        '''
        执行撤单
        '''
        raise(NotImplementedError)