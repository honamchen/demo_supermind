#!/usr/bin/env python
# coding=utf-8
'''
Author: ChenHaonan
Date: 2023-07-14 00:40:01
LastEditors: ChenHaonan
LastEditTime: 2023-07-14 02:11:44
Description: 
'''

import datetime
import numpy as np

def init(context):
    '''
    初始化函数
    *特别说明*:
    - 仅在策略第一次运行时执行
    - 在研究环境中,使用`research_trade`接口执行策略时,第一次运行会在'./persist'路径下生成一个策略同名(用户可自定义传入`research_trade`接口)文件夹,用于持久化全局变量
    - 执行此策略时,如果'./persist'下存在同名路径,则不会执行init
    '''
    select_sentence = '高股息率;peg<1;股价大于3;股价小于15;市值小于100亿' #选股语句
    sort_sentence = '市值从小到大排序' #排序语句
    get_iwencai('{},{}'.format(select_sentence,sort_sentence)) #自然语句选出股票池
    g.max_nums = 10 #最大持股数量
    g.max_tdays = 10 #最大持有时间
    g.stop_gain = 0.2 #止盈
    g.stop_gain_drawdown = 0.05 #回撤止盈
    g.stop_loss = 0.05 #止损
    g.black_stocks = [] #黑名单
    g.holdings = {} # 持股信息
    g.adjust_time = datetime.time(15,30,0) # 允许在几点之前进行买入操作
    
    g.ignore_initstock = False #是否忽略初始持股
    g.sale_initstock = True #是否卖出初始持股
    if not g.ignore_initstock: #不忽略初始持股
        for symbol in context.portfolio.positions:
            g.holdings[symbol] = HoldingInfo(symbol) #将初始持仓写入holdings
            if g.sale_initstock:
                g.holdings[symbol].holding_days = g.max_tdays+1
    log.info('初始化函数运行完毕')


def before_trading(context):
    '''
    开盘前执行,9:00定时执行
    '''
    g.sale_order_ids = {} # 清仓委托信息
    g.buy_order_ids = {} # 建仓委托信息
    g.buy_target = {} # 建仓目标信息
    g.on_exec = {} # 当前执行减仓+持仓数量
    g.sale_finished = [] # 已完成减仓列表
    g.buy_finished = [] # 已完成减仓列表
    g.holding_list = list(g.holdings.keys()) # 持仓列表
    g.st_stocks = get_st_stocks() # st股列表
    log.info('盘前运行完毕')


def open_auction(context,bar_dict):
    '''
    集合竞价后执行,9:26定时执行
    '''
    g.stock_pool = [s for s in context.iwencai_securities if s not in g.st_stocks] # 更新股票池，剔除ST股
    g.stock_pool = g.stock_pool[:g.max_nums] # 取前g.max_nums只股票备用
    log.info('集合竞价后运行完毕')

def handle_bar(context,bar_dict):
    #log.info('{}开始执行'.format(get_datetime().strftime('%Y-%m-%d %H:%M:%S')))
    try: # 尝试
        cancel_order_all() # 撤销全部订单
    except Exception as e: #如果报错
        log.warn(e) # 记录报错信息到日志
    
    # 止盈止损+持有天数达到最大持有天数+更新持仓信息
    for symbol in list(g.holdings.keys()): # 股票持仓
        holding_info = g.holdings.get(symbol) #获取当前轮询代码的持仓信息
        profit_rate = context.portfolio.stock_account.positions[symbol].profit_rate #获取当前盈利
        if profit_rate >= holding_info.max_return: #判断当前收益是否大于历史最大持有收益，如果是
            holding_info.max_return = float(profit_rate) #更新历史最大持有收益
        
        #如果当前轮询代码为触发止盈止损状态且并不是当天买入的股票且股票不在今日选出的股票池中，则
        if not holding_info.stop_gain_or_loss and holding_info.holding_days>1 and symbol not in g.stock_pool:
            if holding_info.holding_days >= g.max_tdays: #判断持有天数是否达到最大持有天数
                holding_info.stop_gain_or_loss = True #如果是,更新止盈止损状态为需要卖出
            if profit_rate >= g.stop_gain or profit_rate <= -g.stop_loss:#判断是否触发止盈或止损
                holding_info.stop_gain_or_loss = True #如果是,更新止盈止损状态为需要卖出
            if profit_rate - holding_info.max_return <= -g.stop_gain_drawdown:#判断是否触发高点回撤止盈
                holding_info.stop_gain_or_loss = True#如果是,更新止盈止损状态为需要卖出
            if symbol in g.black_stocks:#判断是否为黑名单
                holding_info.stop_gain_or_loss = True#如果是,更新止盈止损状态为需要卖出
            if symbol in g.st_stocks:#判断是否被ST或退市等
                holding_info.stop_gain_or_loss = True#如果是,更新止盈止损状态为需要卖出
                
        g.holdings[symbol] = holding_info# 更新持仓信息
        
        # 判断此股票是否需要清仓且目前没有在途清仓委托        
        if g.holdings[symbol].stop_gain_or_loss and g.holdings[symbol].sale_order_id is None:
            order_id = order_target(symbol,0) # 清仓此股票
        
    
    # 时间限制内执行买入
    if get_datetime().time() <= g.adjust_time: # 判断当前是否可以执行买入
        
        target_value = context.portfolio.stock_account.total_value/g.max_nums # 单票最大买入资金
        available_buy_num = g.max_nums + len(g.sale_finished) - len(g.buy_finished) - len(g.holding_list) # 目前剩余可建仓股票数量
        if available_buy_num < 0:
            available_buy_num = 0
        n = 0 # 本轮已委托建仓股票个数
        for symbol in g.stock_pool: # 股票池循环
            if n==available_buy_num: # 如股本次已委托建仓股票个数 与  目前剩余可建仓股票数量 相等
                break # 停止循环，终止建仓
            if symbol in g.buy_finished or symbol in g.holding_list or symbol in list(g.buy_order_ids.values()): # 如果股票今日已建仓完毕,或者,股票今天之前已建仓,或正在建仓中
                continue # 跳过这个股票

            target_volume = aContractDetail[symbol].adjust_vol(target_value/bar_dict[symbol].close,max_limit=False) # 计算目标建仓数量
            g.buy_target[symbol] = target_volume # 更新建仓目标

            v = target_volume - g.on_exec.get(symbol,0) # 计算持仓+目前在途委托 之和 与建仓目标之间的差，为仍需追单的数量
            if v > 0: # 如果需追单数量大于0
                available_cash = context.portfolio.stock_account.available_cash #当前可用现金
                if available_cash>v*bar_dict[symbol].close: # 如果可用现金大于追单所需现金
                    order_id = order(symbol,v) # 追单
                else : # 如果可用现金小于等于追单所需现金
                    v = 100*int(available_cash/bar_dict[symbol].close/100)  # 计算实际可追单数量
                    order_id = order(symbol,v) # 追单
                    break #此时说明已无可用现金,结束循环
            n+=1 # 本轮已委托建仓股票个数+1

# 委托状态更新事件推送
def on_order(context,odr):
    if odr.order_type == SIDE.SELL: #如果推送的委托是清仓委托
        if odr.order_id not in g.sale_order_ids.keys():
            g.sale_order_ids[odr.order_id] = odr.symbol
            g.holdings[odr.symbol].sale_order_id = odr.order_id
        #判断委托状态是否为已撤单或废单
        if odr.status == ORDER_STATUS.REJECTED or odr.status == ORDER_STATUS.CANCELLED:
            g.sale_order_ids.pop(odr.order_id) # 删除清仓委托信息
            g.holdings[odr.symbol].sale_order_id = None # 删除持仓信息中的清仓委托id
        else:#否则
            if odr.filled_amount == odr.amount: # 已成和已报是否相等,若是,则说明股票已清仓
                g.sale_finished.append(odr.symbol)
                g.holdings.pop(odr.symbol) # 删除持仓信息

    if odr.order_type == SIDE.BUY: #如果推送的委托是建仓委托
        if odr.order_id not in g.buy_order_ids.keys():
            g.buy_order_ids[odr.order_id] = odr.symbol
            g.on_exec[odr.symbol] = g.on_exec.get(odr.symbol,0)+odr.amount
        if odr.status == ORDER_STATUS.REJECTED or odr.status == ORDER_STATUS.CANCELLED:
            g.buy_order_ids.pop(odr.order_id)# 删除建仓委托信息
            g.on_exec[odr.symbol] = g.on_exec[odr.symbol]-odr.amount+odr.filled_amount #更新在途委托信息
        else: #否则
            if odr.filled_amount == odr.amount: # 已成和已报是否相等,若是,则说明股票建仓
                g.buy_finished.append(odr.symbol)  # 将代码追加进入已完成建仓股票列表
        
# 成交事件推送
def on_trade(context,trade):
    if trade.side == SIDE.BUY: #买入成交
        if trade.order_book_id not in g.holdings.keys():#是否已记录进持仓信息中，若未记入
            g.holdings[trade.order_book_id] = HoldingInfo(trade.order_book_id) #则记入持仓信息


# 盘后执行
def after_trading(context):
    log.info('盘后运行完毕')
    for symbol in g.holdings.keys():#循环持仓股票
        g.holdings[symbol].holding_days += 1  #持仓天数+1

###------------------------------------------------------------自定义类与函数------------------------------------------------------------###

def get_st_stocks():
    '''
    获取当前bar日期的st股,退市股名单
    '''
    name_info = run_query(
                    query(
                        name_change.symbol,
                        name_change.stock_name
                    ).filter(
                        name_change.change_date <= get_datetime().strftime('%Y-%m-%d')
                    )
                )
    name_info = name_info.groupby('name_change_symbol').last().dropna().iloc[:,0]
    return name_info.loc[name_info.apply(lambda x:'ST' in x or x.startswith('退市') or x.endswith('退'))].index.tolist()

class ContractDetail(object):
    '''
    委托价格、数量规则,目前只适配股票,可以自行拓展
    '''
    MAX_VOLUME = 1000000
    
    def __init__(self, symbol=None):
        if isinstance(symbol, str):
            self.set_symbol(symbol)

    def __getitem__(self, symbol):
        self.set_symbol(symbol)
        return self

    def set_symbol(self, symbol):
        self.symbol = symbol
        self.decimal = self.get_price_decimal()
        self.bvol = self.get_base_vol()
        self.dvol = self.get_delta_vol()

    def get_price_decimal(self):
        return 2

    def get_base_vol(self):
        if self.symbol.startswith('68'): 
            return 200
        else:
            return 100

    def get_delta_vol(self):
        if self.symbol.startswith('68') or self.symbol.endswith('BJ'):
            return 1
        else:
            return 100

    def get_dot(self):
        # A股
        return 1

    def adjust_vol(self, vol, available=None,max_limit=True):
        if vol > 0:
            if vol > self.MAX_VOLUME and max_limit:
                return self.MAX_VOLUME
            xbase = int(np.round(vol/self.bvol,2))*self.bvol
            if xbase == 0:
                return 0
            xdelta = int(
                np.round(1.0*(max(vol - xbase, 0))/self.dvol))*self.dvol
            return xbase+xdelta
        elif vol < 0:
            xvol = -self.adjust_vol(-vol,available=available,max_limit=max_limit)
            if available is None:
                return xvol
            elif available <= abs(vol):
                return -available
            elif available <= abs(xvol):
                return -available
            else:
                return xvol
        else:
            return 0

    def adjust_price(self, price):
        return float(
            (
                '%%.%df' % (self.decimal)
            ) % np.round(price, self.decimal)
        )

    def print_detail(self):
        print(
            '代码:%s,最小股数：%d,增量股数：%d,最小报价单位：%d' % (
                self.symbol, self.bvol, self.dvol, self.decimal)
        )
        
aContractDetail = ContractDetail()

#构造HoldingInfo类,记录买入股票的信息,可自定义需要记录的信息
class HoldingInfo(object):
    '''
    补充持仓信息
    @symbol:股票代码
    @holding_days:持有天数,买入当天为第0天
    @stop_gain_or_loss:是否触发卖出条件
    @max_return:最大持有收益率
    @sale_order_id:清仓委托id
    '''
    def __init__(self,symbol):
        self._symbol = symbol
        self._holding_days = 0
        self._stop_gain_or_loss = False
        self._max_return = 0.0
        self._sale_order_id = None
        
    @property    
    def symbol(self):
        return self._symbol

    @property    
    def holding_days(self):
        return self._holding_days
        
    @holding_days.setter   
    def holding_days(self,value):
        a = value
        if a is not None and isinstance(a, int): 
            self._holding_days = a
        else:
            raise ValueError('holding_days必须为int类型')
    
    @property    
    def stop_gain_or_loss(self):
        return self._stop_gain_or_loss
        
    @stop_gain_or_loss.setter   
    def stop_gain_or_loss(self,value):
        a = value
        if a is not None and isinstance(a, bool): 
            self._stop_gain_or_loss = a
        else:
            raise ValueError('stop_gain_or_loss必须为bool类型')
    
    @property    
    def max_return(self):
        return self._max_return
        
    @max_return.setter   
    def max_return(self,value):
        a = value
        if a is not None and isinstance(a, float): 
            self._max_return = a
        else:
            raise ValueError('max_return必须为float类型')
            
    @property    
    def sale_order_id(self):
        return self._sale_order_id
        
    @sale_order_id.setter   
    def sale_order_id(self,value):
        a = value
        if a is None or isinstance(a, str): 
            self._sale_order_id = a
        else:
            raise ValueError('sale_order_id必须为str类型')
        