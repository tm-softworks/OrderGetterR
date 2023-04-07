
import os
import sys
from collections import OrderedDict
from datetime import datetime, timedelta
import calendar
from argparse import ArgumentParser
import configparser
import traceback
import time
import csv
import io
import copy
import hashlib
import logging
import logging.handlers
import pytz

from rakuten_ws import RakutenWebService
import zeep
from zeep.helpers import serialize_object

JST = pytz.timezone('Asia/Tokyo')

logger = logging.getLogger()
config = None

OUTPUT_KEY = 'output.'
GET_ORDER_ROOT_KEY = 'getOrderRequestModel'
GET_ORDER_SEARCH_ROOT_KEY = 'orderSearchModel'
ORDER_SEARCH_START_DATE_KEY = 'startDate'
ORDER_SEARCH_END_DATE_KEY = 'endDate'
ORDER_SEARCH_START_DATETIME_KEY = 'startDatetime'
ORDER_SEARCH_END_DATETIME_KEY = 'endDatetime'
GENERAL_SECTION_KEY = 'general'
GENERAL_PERIOD_KEY = 'period'
GENERAL_DURATION_1CALL_KEY = 'duration'
GENERAL_THIS_MONTH_KEY = 'thisMonth'
GENERAL_PREV_MONTH_KEY = 'prevMonth'
GENERAL_GET_ORDER_VERSION_KEY = 'getOrderVersion'
GET_ORDER_COUNT_LIMIT = 100

class OrderList:

  def __init__(self):
    self.targetShop = []
    self.isTest = False
    self.defaultConfigFile = 'setting.ini'
    self.version = '1.0.1'
    self.myname = 'OrderList'
    self.config = None

  def initLog(self, logPath):
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(threadName)s - %(lineno)s - %(name)s - %(message)s')
    rfh = logging.handlers.RotatingFileHandler(
      filename=logPath,
      maxBytes=10*1024*1024,
      backupCount=7
    )
    rfh.setLevel(logging.DEBUG)
    rfh.setFormatter(formatter)
    logger.addHandler(rfh)
    logger.debug('initLog')

  def parser(self):
    usage = 'Usage: %(prog)s [option] input_file'
    argparser = ArgumentParser(usage=usage,
                               epilog="""
                                 Copyright (C) 2017 T.M SoftWorks ( tm.softworks.info@gmail.com )
                                 """)
    argparser.add_argument('input_file')
    argparser.add_argument('-v', '--verbose',
                           action='store_true',
                           help='show verbose message')
    argparser.add_argument('-c', '--conf', type=str,
                           dest='config_file',
                           default=self.defaultConfigFile,
                           help='config file name')
    argparser.add_argument('-p', '--coupon',
                           action='store_true',
                           help='coupon detail')
    argparser.add_argument('-s', '--shipping-detail',
                           action='store_true',
                           help='shipping detail')
    argparser.add_argument('-d', '--dry-run',
                           action='store_true',
                           help='dry run')
    argparser.add_argument('--version',
                           action='version',
                           version='%(prog)s '+self.version)
    
    args = argparser.parse_args()
    return args

  def emptyConfig(self):
    condition = configparser.ConfigParser()
    condition['global'] = {}
    condition['api'] = {}
    return condition
  
  def defaultConfigPart(self, conf, key, value):
    if not key in conf: conf[key] = value

  def defaultConfig(self, conf):
    g = conf['global']
    self.defaultConfigPart(g, 'logDir', './logs')
    self.defaultConfigPart(g, 'logFile', 'orderlist.log')
    self.defaultConfigPart(g, 'outDir', './data')

    a = conf['api']
    self.defaultConfigPart(a, 'User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36')
    self.defaultConfigPart(a, 'input_encoding', 'cp932')
    self.defaultConfigPart(a, 'output_encoding', 'cp932')
    self.defaultConfigPart(a, 'input_delimiter', ',')
    self.defaultConfigPart(a, 'input_quotechar', '"')
    self.defaultConfigPart(a, 'output_delimiter', ',')
    self.defaultConfigPart(a, 'output_quotechar', '"')
    self.defaultConfigPart(a, 'continue_errorcode', 'N00-000,W00-000,E10-001')
    self.defaultConfigPart(a, 'nothing_errorcode', 'E10-001')
    self.defaultConfigPart(a, 'warning_errorcode', 'W00-000')
    self.defaultConfigPart(a, 'call_per_sec', '1')
    self.defaultConfigPart(a, 'list_keys', 'orderNumber,status,orderType,mailAddressType,pointStatus,rbankStatus,orderSite,enclosureStatus,cardStatus,payType')
    self.defaultConfigPart(a, 'list_number_keys', 'orderProgressList,subStatusIdList,orderTypeList')
    self.defaultConfigPart(a, 'date_keys', 'startDate,endDate')
    self.defaultConfigPart(a, 'datetime_keys', 'startDatetime,endDatetime')
    self.defaultConfigPart(a, 'bool_keys', 'isOrderNumberOnlyFlg,pointUsed,modify,asuraku,coupon')
    self.defaultConfigPart(a, 'number_keys', 'dateType,settlementMethod,shippingDateBlankFlag,shippingNumberBlankFlag,searchKeywordType,mailSendType,phoneNumberType,purchaseSiteType,asurakuFlag,couponUseFlag,drugFlag,overseasFlag,requestRecordsAmount,requestPage,sortColumn,sortDirection')
    self.defaultConfigPart(a, 'parse_format', '%%Y/%%m/%%d %%H:%%M:%%S')
    self.defaultConfigPart(a, 'parse_format_datetime', '%%Y-%%m-%%dT%%H:%%M:%%S%%z')
    self.defaultConfigPart(a, 'datetime_format', '{0:%%Y/%%m/%%d %%H:%%M:%%S}')
    self.defaultConfigPart(a, 'RPay', '0')
    self.defaultConfigPart(a, 'getOrderVersion', '1')
  
  
  prev_apicall = None
  def getOrderTest(self):
    return {
      'errorCode': 'N00-000',
      'message': '\u6b63\u5e38\u7d42\u4e86',
      'unitError': [],
      'orderModel': [{
        'childOrderModel': [],
        'couponModel': [{
          'couponCode': 'COUPON1',  
        }],
        'packageModel': []
      }]}

  
  def getRmsService(self, conf):
    credentials = {
      'license_key': conf['licenseKey'],
      'secret_service': conf.get('serviceSecret') or conf.get('secretService'),
      'shop_url': conf['shopUrl'],
    }
    ws = RakutenWebService(**credentials)
    ua = 'OrderListClient/1.0.1'
    if conf['RPay'] == '0':
      ws.rms.order.zeep_client.transport.session.headers['User-Agent'] = ua
    else:
      ws.rms.rpay.search_order.client.service.webservice.session.headers['User-Agent'] = ua
      ws.rms.rpay.get_order.client.service.webservice.session.headers['User-Agent'] = ua
  
    return ws
  
  def genLicense(self, a, s):
    source = (a+s).encode('utf-8')
    return hashlib.sha256(source).hexdigest()
  
  def checkShopUrl(self, conf):
    tareget = ''
    s = conf['api']['shopUrl']

  def checkTargetShop(self, conf):
    s = conf['api']['shopUrl'] 
    for shop in self.targetShop:
      if s.startswith(shop):
        return True

    return False

  def getOrder(self, ws, input_dict, conf):
    logger.info('getOrder start')
    logger.debug('getOrder: {}'.format(input_dict))

    wait_sec = int(conf['call_per_sec'])
    args = input_dict[GET_ORDER_ROOT_KEY]
    self.prev_apicall = self.waitSec(self.prev_apicall, wait_sec)
    ret = ws.rms.order.getOrder(**args)
    if 'errorCode' in ret and not ret['errorCode'] in ['N00-000', 'W00-000']:
      logger.error('{}'.format(ret))
      #logger.debug(ws.ichiba.item.search(keyword='4562373379528'))
    logger.debug(ret)
    return ret
  
  def getOrderRPay(self, ws, input_dict, conf):
    logger.info('getOrderRPay start')
    logger.debug('getOrderRPay: {}'.format(input_dict))

    wait_sec = int(conf['call_per_sec'])
    args = input_dict[GET_ORDER_ROOT_KEY]
    if 'startDate' in args[GET_ORDER_SEARCH_ROOT_KEY]:
      args['startDatetime'] = args[GET_ORDER_SEARCH_ROOT_KEY]['startDate']
    if 'endDate' in args[GET_ORDER_SEARCH_ROOT_KEY]:
      args['endDatetime'] = args[GET_ORDER_SEARCH_ROOT_KEY]['endDate']
    del args[GET_ORDER_SEARCH_ROOT_KEY]
    self.prev_apicall = self.waitSec(self.prev_apicall, wait_sec)
    ret = ws.rms.rpay.search_order(**args)
    logger.debug('search_order result: {}'.format(vars(ret)))
    if 'errorCode' in ret and not ret['errorCode'] in ['N00-000', 'W00-000']:
      logger.error('{}'.format(ret))
      #logger.debug(ws.ichiba.item.search(keyword='4562373379528'))
    logger.debug(vars(ret))
    logger.debug(ret.get('orderNumberList'))

    result_array = []
    if 'orderNumberList' in ret and len(ret['orderNumberList']) > 0:
      orderNumberList = ret['orderNumberList']
      index = 0
      while True:
        targetList = orderNumberList[index:index+GET_ORDER_COUNT_LIMIT]
        logger.info('get_order: {} - {}'.format(index, index + len(targetList) - 1))
        if len(targetList) == 0:
          break

        index += len(targetList)

        args = {"orderNumberList": targetList}
        if GENERAL_GET_ORDER_VERSION_KEY in conf:
          args["version"] = conf[GENERAL_GET_ORDER_VERSION_KEY]
        self.prev_apicall = self.waitSec(self.prev_apicall, wait_sec)
        ret2 = ws.rms.rpay.get_order(**args)
        logger.debug('get_order result: {}'.format(vars(ret2)))
        messages = ret2["MessageModelList"]
        result_array.extend(ret2["OrderModelList"])
        
        logger.info('get_order: {}'.format(len(targetList)))

        if len(targetList) < GET_ORDER_COUNT_LIMIT:
          break

      return {'orderModel': result_array, 'errorCode': 'N00-000', 'message': 'Found'}
    else:
      ret['errorCode'] = 'W00-000'
      ret['message'] = 'Not Found'
      ret['orderModel'] = []
    return ret
  
  def to_bool(self, s):
    return False if s.lower() in ['false', '0'] else True
  
  def datetimeJST(self, year, month, day, hour=0, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=JST)
  
  def add_months(self, sourcedate, months):
    month = sourcedate.month - 1 + months
    year = int(sourcedate.year + month / 12 )
    month = month % 12 + 1
    day = min(sourcedate.day,calendar.monthrange(year, month)[1])
    return datetime(year,month,day)
  
  def readOutputColumn(self, condition):
    logger.debug("readOutputColumn")
    new_dict = OrderedDict()
    for section in condition.sections():
      if section.startswith(OUTPUT_KEY):
        keys = section.split('.')
        if len(keys) >= 2 and (keys[1] == 'orderModel' or keys[1] == 'OrderModelList'):
          prefix = ".".join(keys[2:])
          if len(prefix): prefix += "."
          for key in condition[section]:
            val = condition[section][key]
            new_dict[prefix+key] = val
            logger.debug(new_dict)
    return new_dict
  
  def readCondition(self, config, condition):
    list_keys = config['api']['list_keys'].split(',')
    list_number_keys = config['api']['list_number_keys'].split(',')
    date_keys = config['api']['date_keys'].split(',')
    datetime_keys = config['api']['datetime_keys'].split(',')
    bool_keys = config['api']['bool_keys'].split(',')
    number_keys = config['api']['number_keys'].split(',')
    
    new_hash = {}
    for section in condition.sections():
      if section.startswith(GET_ORDER_ROOT_KEY):
        new_dict = {}
        for key in condition[section]:
          val = condition[section][key]
          if not len(val) == 0:
            if key in list_keys:
              new_dict[key] = val.split(',')
            elif key in list_number_keys:
              s = val.split(',')
              new_dict[key] = [int(i) for i in s]
            elif key in date_keys:
              parse_format = config['api']['parse_format']
              new_dict[key] = JST.localize(datetime.strptime(val, parse_format))
            elif key in datetime_keys:
              parse_format = config['api']['parse_format_datetime']
              new_dict[key] = datetime.strptime(val, parse_format)
            elif key in bool_keys:
              new_dict[key] = self.to_bool(val)
            elif key in number_keys:
              new_dict[key] = int(val)
            else:
              new_dict[key] = val
        if len(new_dict):
          keys = section.split('.')
          tmp_hash = new_hash
          for k in keys:
            if not k in tmp_hash:
              tmp_hash[k] = {}
            tmp_hash = tmp_hash[k]
          tmp_hash.update(new_dict)
  
    general_conf = {}
  
    if GENERAL_SECTION_KEY in condition.sections():
      if not GET_ORDER_ROOT_KEY in new_hash:
        new_hash[GET_ORDER_ROOT_KEY] = {}
      if not GET_ORDER_SEARCH_ROOT_KEY in new_hash[GET_ORDER_ROOT_KEY]:
        new_hash[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY] = {}
  
      if GENERAL_DURATION_1CALL_KEY in condition[GENERAL_SECTION_KEY]:
        general_conf[GENERAL_DURATION_1CALL_KEY] = condition[GENERAL_SECTION_KEY][GENERAL_DURATION_1CALL_KEY]
      if GENERAL_PERIOD_KEY in condition[GENERAL_SECTION_KEY]:
        period = condition[GENERAL_SECTION_KEY][GENERAL_PERIOD_KEY]
        if len(period):
          toDate = JST.localize(datetime.now())
          fd = toDate - timedelta(days=int(period))
          fromDate = JST.localize(datetime(fd.year, fd.month, fd.day))
          logger.debug('{} - {}'.format(fromDate, toDate))
          new_hash[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_START_DATE_KEY] = fromDate
          new_hash[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_END_DATE_KEY] = toDate

        prevMonth = condition[GENERAL_SECTION_KEY][GENERAL_PREV_MONTH_KEY]
        if prevMonth == "1":
          now = JST.localize(datetime.now())
          fd = self.add_months(now, -1)
          fromDate = JST.localize(datetime(fd.year, fd.month, 1))
          toDateTmp = JST.localize(datetime(now.year, now.month, 1, 23, 59, 59))
          toDate = toDateTmp - timedelta(days=1)
          logger.debug('{} - {}'.format(fromDate, toDate))
          new_hash[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_START_DATE_KEY] = fromDate
          new_hash[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_END_DATE_KEY] = toDate

        thisMonth = condition[GENERAL_SECTION_KEY][GENERAL_THIS_MONTH_KEY]
        if thisMonth == "1":
          toDate = JST.localize(datetime.now())
          fromDate = JST.localize(datetime(toDate.year, toDate.month, 1))
          logger.debug('{} - {}'.format(fromDate, toDate))
          new_hash[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_START_DATE_KEY] = fromDate
          new_hash[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_END_DATE_KEY] = toDate
    return (new_hash, general_conf)
  
  def genFileName(self, key, outPath='.', ext='csv'):
    now = datetime.now()
    name = "{3}/{0:%Y%m%d_%H%M%S}_{1}.{2}".format(now, key, ext, outPath)
    return name
  
  def datetimeSplit(self, start, end, duration):
    if duration < 0:
      return [{'start': start, 'end': end}]
    result = []
    s = start
    while True:
      e = s + timedelta(seconds=(duration - 1))
      if e > end: e = end
      result.append({'start': s, 'end': e})
      if e == end: break
      s = e + timedelta(seconds=1)
      logger.debug('datetimeSplit: {}'.format(result))
    return result
  
  def readInput(self, config, input_file):
    condition = configparser.ConfigParser()
    condition.optionxform = str
    condition.read(input_file, encoding='cp932')
  
    (hash, general_conf) = self.readCondition(config, condition)
    outputColumns = self.readOutputColumn(condition)
    
    return (hash, outputColumns, general_conf)
  
  def quotedValue(self, data, qc='"'):
    return qc+data+qc
  
  def quotedAppendList(self, _list, qc, data):
    _list.append(data)
    #  _list.append(qc + data + qc)
  
  def waitSec(self, prev, maxWait = 3):
    now = time.time()
    if prev != None:
      sec = now - prev
      ssec = maxWait - sec
      if ssec > 0:
        logger.debug('sleep: {}, sleep={}'.format(sec, ssec))
        time.sleep(ssec)
    return now
  
  def findObj(self, obj, path):
    keys = path.split('.')
    d = obj
    for k in keys:
      if k in d:
        d = d[k]
    return d if d != obj else None
  
  def grabChildren(self, father, prefix = ""):
    local_list = {}
    if not isinstance(father, dict): return local_list
    for key, value in father.items():
      #local_list.append(key)
      if isinstance(value, dict):
        local_list.update(self.grabChildren(value, prefix+key+"."))
      elif isinstance(value, list):
        local_list[prefix+key] = value
      else:
        local_list[prefix+key] = value
    return local_list
  
  def extendOrder(self, orderModel):
    '''
    orderModel[]
      packageModel[]
        itemModel[]
    '''
  
    extendedOrderModel = []
    order_dict = self.grabChildren(orderModel)
    key1 = 'packageModel' if 'packageModel' in orderModel else 'PackageModelList'
    for packageModel in orderModel[key1]:
      prefix = key1+'.'
      logger.debug('{}'.format(packageModel))
      pkg_dict = self.grabChildren(packageModel, prefix)
      key2 = 'itemModel' if 'itemModel' in packageModel else 'ItemModelList'
      for itemModel in packageModel[key2]:
        prefix = key1+'.'+key2+'.'
        item_dict = self.grabChildren(itemModel, prefix)
        new_dict = copy.copy(order_dict)
        new_dict.update(pkg_dict)
        new_dict.update(item_dict)

        key3 = 'skuModel' if 'skuModel' in itemModel else 'SkuModelList'
        if itemModel.get(key3) is not None:
          for skuModel in itemModel[key3]:
            prefix = key1+'.'+key2+'.'+key3+'.'
            sku_dict = self.grabChildren(skuModel, prefix)
            new_dict.update(sku_dict)

        extendedOrderModel.append(new_dict)
  
    return extendedOrderModel
  
  def writeOutput(self, conf, output_file, output_columns, result, writeHeader):
    logger.debug("writeOutput: rows={}".format(len(result)))
    csv_writer = csv.writer(
      output_file,
      #sys.stdout,
      dialect='excel',
      lineterminator='\n',
      delimiter=conf['output_delimiter'],
      quotechar=conf['output_quotechar'],
      quoting=csv.QUOTE_ALL,
    )
  
    datetime_format = conf['datetime_format']
    headers = []
    listOrderModel = result['orderModel']
    linum = 0
    for (index, orderModelObj) in enumerate(listOrderModel):
      logger.debug('{}: {}'.format(index, orderModelObj))
      if conf['RPay'] == '0':
        orderModel = zeep.helpers.serialize_object(orderModelObj)
      else:
        orderModel = orderModelObj
      if isinstance(orderModel, dict):
        extendedOrderModel = self.extendOrder(orderModel)
        for eo in extendedOrderModel:
          cols = []
          for (oc, col) in output_columns.items():
            if oc.find('couponModel') < 0 and oc.find('childOrderModel') < 0 and oc.find('CouponModelList') < 0:
              if linum == 0: headers.append(col)
              v = ""
              if oc in eo:
                if isinstance(eo[oc], datetime):
                  v = datetime_format.format(eo[oc])
                else:
                  v = eo[oc]
              cols.append(v)
          if linum == 0 and writeHeader: csv_writer.writerow(headers)
          csv_writer.writerow(cols)
          linum += 1

    return linum

  def extendCouponDetail(self, orderModel):
    '''
    orderModel[]
      couponModel[]
    '''
  
    extendedCouponModel = []
    order_dict = self.grabChildren(orderModel)
    key1 = 'couponModel' if 'couponModel' in orderModel else 'CouponModelList'
    if orderModel[key1] is not None:
      for packageModel in orderModel[key1]:
        prefix = key1+'.'
        logger.debug('{}'.format(packageModel))
        pkg_dict = self.grabChildren(packageModel, prefix)
        new_dict = copy.copy(order_dict)
        new_dict.update(pkg_dict)
        extendedCouponModel.append(new_dict)
  
    return extendedCouponModel

  def writeCouponDetail(self, conf, output_file, output_columns, result, writeHeader):
    if not output_file: return 0
  
    logger.debug("writeCouponDetail: rows={}".format(len(result)))
    csv_writer = csv.writer(
      output_file,
      #sys.stdout,
      dialect='excel',
      lineterminator='\n',
      delimiter=conf['output_delimiter'],
      quotechar=conf['output_quotechar'],
      quoting=csv.QUOTE_ALL,
    )
  
    datetime_format = conf['datetime_format']
    headers = []
    listOrderModel = result['orderModel']
    linum = 0
    for (index, orderModelObj) in enumerate(listOrderModel):
      logger.debug('{}: {}'.format(index, orderModelObj))
      orderModel = zeep.helpers.serialize_object(orderModelObj)
      if isinstance(orderModel, dict):
        extendedCouponModel = self.extendCouponDetail(orderModel)
        for eo in extendedCouponModel:
          cols = []
          for (oc, col) in output_columns.items():
            if oc.find('coupon') >= 0 or oc.find('orderNumber') >= 0:
              if linum == 0: headers.append(col)
              v = ""
              if oc in eo:
                if isinstance(eo[oc], datetime):
                  v = datetime_format.format(eo[oc])
                else:
                  v = eo[oc]
              cols.append(v)
            else:
              continue
          if linum == 0 and writeHeader: csv_writer.writerow(headers)
          csv_writer.writerow(cols)
          linum += 1
    return linum

  def extendShippingDetail(self, orderModel):
    '''
    orderModel[]
      shippingModel[]
    '''

    extendedShippingModel = []
    order_dict = self.grabChildren(orderModel)
    key1 = 'packageModel' if 'packageModel' in orderModel else 'PackageModelList'
    for packageModel in orderModel[key1]:
      prefix = key1+'.'
      logger.debug('{}'.format(packageModel))
      pkg_dict = self.grabChildren(packageModel, prefix)
      key2 = 'ShippingModelList'
      if packageModel.get(key2) is not None:
        for packageModel in packageModel[key2]:
          prefix = key1+'.'+key2+'.'
          logger.debug('{}'.format(packageModel))
          item_dict = self.grabChildren(packageModel, prefix)
          new_dict = copy.copy(order_dict)
          new_dict.update(pkg_dict)
          new_dict.update(item_dict)
          extendedShippingModel.append(new_dict)
    return extendedShippingModel

  def writeShippingDetail(self, conf, output_file, output_columns, result, writeHeader):
    if not output_file: return 0

    logger.debug("writeShippingDetail: rows={}".format(len(result)))
    csv_writer = csv.writer(
      output_file,
      #sys.stdout,
      dialect='excel',
      lineterminator='\n',
      delimiter=conf['output_delimiter'],
      quotechar=conf['output_quotechar'],
      quoting=csv.QUOTE_ALL,
    )
    datetime_format = conf['datetime_format']
    headers = []
    listOrderModel = result['orderModel']
    linum = 0
    for (index, orderModelObj) in enumerate(listOrderModel):
      logger.debug('{}: {}'.format(index, orderModelObj))
      orderModel = zeep.helpers.serialize_object(orderModelObj)
      if isinstance(orderModel, dict):
        extendedShippingModel = self.extendShippingDetail(orderModel)
        for eo in extendedShippingModel:
          cols = []
          for (oc, col) in output_columns.items():
            if oc.find('ShippingModelList') >= 0 or oc.find('orderNumber') >= 0 or oc.find('basketId') >= 0:
              if linum == 0: headers.append(col)
              v = ""
              if oc in eo:
                if isinstance(eo[oc], datetime):
                  v = datetime_format.format(eo[oc])
                else:
                  v = eo[oc]
              cols.append(v)
            else:
              continue
          if linum == 0 and writeHeader: csv_writer.writerow(headers)
          csv_writer.writerow(cols)
          linum += 1
    return linum

  def main(self):
    ol = OrderList()
    try:
      args = self.parser()
      config = configparser.ConfigParser()
      config.read(args.config_file, encoding='cp932')
      self.defaultConfig(config)

      logDir = config['global']['logDir']
      logFile = config['global']['logFile']
      outDir = config['global']['outDir']
      continueErrorCode = config['api']['continue_errorcode'].split(',')
      nothingErrorCode = config['api']['nothing_errorcode'].split(',')
      warningErrorCode = config['api']['warning_errorcode'].split(',')
      rpay = True if config['api']['RPay'] == '1' else False
  
  
      os.makedirs(logDir, exist_ok=True)
      os.makedirs(outDir, exist_ok=True)
      self.initLog('{}/{}'.format(logDir, logFile))
      logger.info('start')
      if args.verbose:
        logger.setLevel(logging.DEBUG)
      else:
        logger.setLevel(logging.INFO)
  
      logger.debug(args)
  
      # read input
      (input_dict, output_columns, general_conf) = self.readInput(config, args.input_file)

      if ORDER_SEARCH_START_DATE_KEY in input_dict[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY]:
        start = input_dict[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_START_DATE_KEY]
      else:
        start = input_dict[GET_ORDER_ROOT_KEY]['startDatetime']

      if ORDER_SEARCH_END_DATE_KEY in input_dict[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY]:
        end = input_dict[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_END_DATE_KEY]
      else:
        end = input_dict[GET_ORDER_ROOT_KEY]['endDatetime']

      duration_1call = -1
      if GENERAL_DURATION_1CALL_KEY in general_conf:
        val = general_conf[GENERAL_DURATION_1CALL_KEY]
        if val: duration_1call = int(val)
  
      datetimeList = self.datetimeSplit(start, end, duration_1call)
  
      ws = self.getRmsService(config['api'])

      total_output = 0
      index = 0
      outfile = self.genFileName('order', outDir)
      couponfile = self.genFileName('coupon', outDir)
      shippingfile = self.genFileName('shipping', outDir)
      coupon = args.coupon
      coupon_file = None
      shipping = args.shipping_detail
      shipping_file = None
      writeCouponHeader = True
      writeShippingHeader = True
      with io.open(outfile, "w", encoding=config['api']['output_encoding'], errors='replace') as output_file:
        if coupon:
          coupon_file = io.open(couponfile, "w", encoding=config['api']['output_encoding'], errors='replace')
        if shipping:
          shipping_file = io.open(shippingfile, "w", encoding=config['api']['output_encoding'], errors='replace')
        for dt in datetimeList:
          if not GET_ORDER_SEARCH_ROOT_KEY in input_dict[GET_ORDER_ROOT_KEY]:
            input_dict[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY] = {}
          input_dict[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_START_DATE_KEY] = dt['start']
          input_dict[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_END_DATE_KEY] = dt['end']
          logger.debug(input_dict)
          result = None
          if not args.dry_run:
            if rpay:
              result = self.getOrderRPay(ws, input_dict, config['api'])
            else:
              result = self.getOrder(ws, input_dict, config['api'])
          else:
            ss = "{0:%Y/%m/%d %H:%M:%S}".format(dt['start'])
            es = "{0:%Y/%m/%d %H:%M:%S}".format(dt['end'])
            print('getOrder: {} - {}'.format(ss, es))
            result = self.getOrderTest()
  
          if 'errorCode' in result and not result['errorCode'] in continueErrorCode:
            err = '{}: {}'.format(result['errorCode'], result['message'])
            print('  {}'.format(err))
            logger.error('{}'.format(err))
            #logger.error('unitError: {}'.format(result['unitError']))
            raise Exception(err)
          elif 'errorCode' in result and result['errorCode'] in nothingErrorCode:
            warn = '{}: {}'.format(result['errorCode'], result['message'])
            logger.warn(warn)
            continue
          elif 'errorCode' in result and result['errorCode'] in warningErrorCode:
            warn = '{}: {}'.format(result['errorCode'], result['message'])
            print('  {}'.format(warn))
            logger.warn('{}'.format(warn))
            #logger.warn('unitError: {}'.format(result['unitError']))
            if not len(result['orderModel']):
              continue

          cnt = self.writeOutput(config['api'], output_file,
                                 output_columns, result, index == 0)
          total_output += cnt
          print('  Write Success: line={}'.format(cnt))
          cwnum = self.writeCouponDetail(config['api'], coupon_file,
                                         output_columns, result, writeCouponHeader)
          if cwnum > 0:
            writeCouponHeader = False

          cwnum = self.writeShippingDetail(config['api'], shipping_file,
                                         output_columns, result, writeShippingHeader)
          if cwnum > 0:
            writeShippingHeader = False
          index += 1
  
    except Exception as e:
      print('  {}'.format(e))
      logger.error(e)
      logger.error(traceback.format_exc())
  
    logger.info('end')


