
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

JST = pytz.timezone('Asia/Tokyo')

logger = logging.getLogger()
config = None

OUTPUT_KEY = 'output.'
GET_ORDER_ROOT_KEY = 'getOrderRequestModel'
GET_ORDER_SEARCH_ROOT_KEY = 'orderSearchModel'
ORDER_SEARCH_START_DATE_KEY = 'startDate'
ORDER_SEARCH_END_DATE_KEY = 'endDate'
GENERAL_SECTION_KEY = 'general'
GENERAL_PERIOD_KEY = 'period'
GENERAL_DURATION_1CALL_KEY = 'duration'
GENERAL_THIS_MONTH_KEY = 'thisMonth'
GENERAL_PREV_MONTH_KEY = 'prevMonth'

class OrderList:

  def __init__(self):
    self.targetShop = []
    self.isTest = False
    self.defaultConfigFile = 'setting.ini'
    self.version = '1.0.1'
    self.myname = 'OrderList'

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
    self.defaultConfigPart(a, 'date_keys', 'startDate,endDate')
    self.defaultConfigPart(a, 'bool_keys', 'isOrderNumberOnlyFlg,pointUsed,modify,asuraku,coupon')
    self.defaultConfigPart(a, 'parse_format', '%%Y/%%m/%%d %%H:%%M:%%S')
    self.defaultConfigPart(a, 'datetime_format', '{0:%%Y/%%m/%%d %%H:%%M:%%S}')
  
  
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
      'secret_service': conf['secretService'],
      'shop_url': conf['shopUrl'],
    }
    ws = RakutenWebService(**credentials)
    ws.rms.order.zeep_client.transport.session.headers['User-Agent'] = 'OrderListClient/1.0'
  
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
        if len(keys) >= 2 and keys[1] == 'orderModel':
          prefix = ".".join(keys[2:])
          if len(prefix): prefix += "."
          for key in condition[section]:
            val = condition[section][key]
            new_dict[prefix+key] = val
            logger.debug(new_dict)
    return new_dict
  
  def readCondition(self, config, condition):
    list_keys = config['api']['list_keys'].split(',')
    date_keys = config['api']['date_keys'].split(',')
    bool_keys = config['api']['bool_keys'].split(',')
    
    new_hash = {}
    for section in condition.sections():
      if section.startswith(GET_ORDER_ROOT_KEY):
        new_dict = {}
        for key in condition[section]:
          val = condition[section][key]
          if not len(val) == 0:
            if key in list_keys:
              new_dict[key] = val.split(',')
            elif key in date_keys:
              parse_format = config['api']['parse_format']
              new_dict[key] = datetime.strptime(val, parse_format).replace(tzinfo=JST)
            elif key in bool_keys:
              new_dict[key] = self.to_bool(val)
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
          toDate = datetime.now().replace(tzinfo=JST)
          fd = toDate - timedelta(days=int(period))
          fromDate = datetime(fd.year, fd.month, fd.day).replace(tzinfo=JST)
          logger.debug('{} - {}'.format(fromDate, toDate))
          new_hash[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_START_DATE_KEY] = fromDate
          new_hash[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_END_DATE_KEY] = toDate

        prevMonth = condition[GENERAL_SECTION_KEY][GENERAL_PREV_MONTH_KEY]
        if prevMonth == "1":
          now = datetime.now().replace(tzinfo=JST)
          fd = self.add_months(now, -1)
          fromDate = datetime(fd.year, fd.month, 1).replace(tzinfo=JST)
          toDateTmp = datetime(now.year, now.month, 1, 23, 59, 59).replace(tzinfo=JST)
          toDate = toDateTmp - timedelta(days=1)
          logger.debug('{} - {}'.format(fromDate, toDate))
          new_hash[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_START_DATE_KEY] = fromDate
          new_hash[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_END_DATE_KEY] = toDate

        thisMonth = condition[GENERAL_SECTION_KEY][GENERAL_THIS_MONTH_KEY]
        if thisMonth == "1":
          toDate = datetime.now().replace(tzinfo=JST)
          fromDate = datetime(toDate.year, toDate.month, 1).replace(tzinfo=JST)
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
    for packageModel in orderModel['packageModel']:
      prefix = 'packageModel.'
      logger.debug('{}'.format(packageModel))
      pkg_dict = self.grabChildren(packageModel, prefix)
      for itemModel in packageModel['itemModel']:
        prefix = 'packageModel.itemModel.'
        item_dict = self.grabChildren(itemModel, prefix)
        new_dict = copy.copy(order_dict)
        new_dict.update(pkg_dict)
        new_dict.update(item_dict)
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
      orderModel = zeep.helpers.serialize_object(orderModelObj)
      if isinstance(orderModel, dict):
        extendedOrderModel = self.extendOrder(orderModel)
        for eo in extendedOrderModel:
          cols = []
          for (oc, col) in output_columns.items():
            if oc.find('couponModel') < 0 and oc.find('childOrderModel') < 0:
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
    for packageModel in orderModel['couponModel']:
      prefix = 'couponModel.'
      logger.debug('{}'.format(packageModel))
      pkg_dict = self.grabChildren(packageModel, prefix)
      new_dict = copy.copy(order_dict)
      new_dict.update(pkg_dict)
      extendedCouponModel.append(new_dict)
  
    return extendedCouponModel

  def writeCouponDetail(self, conf, output_file, output_columns, result, writeHeader):
    if not output_file: return
  
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
  
      start = input_dict[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_START_DATE_KEY]
      end = input_dict[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_END_DATE_KEY]
  
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
      coupon = args.coupon
      coupon_file = None
      writeCouponHeader = True
      with io.open(outfile, "w", encoding=config['api']['output_encoding'], errors='replace') as output_file:
        if coupon:
          coupon_file = io.open(couponfile, "w", encoding=config['api']['output_encoding'], errors='replace')
        for dt in datetimeList:
          input_dict[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_START_DATE_KEY] = dt['start']
          input_dict[GET_ORDER_ROOT_KEY][GET_ORDER_SEARCH_ROOT_KEY][ORDER_SEARCH_END_DATE_KEY] = dt['end']
          logger.debug(input_dict)
          result = None
          if not args.dry_run:
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
            logger.error('unitError: {}'.format(result['unitError']))
            raise Exception(err)
          elif 'errorCode' in result and result['errorCode'] in nothingErrorCode:
            warn = '{}: {}'.format(result['errorCode'], result['message'])
            logger.warn(warn)
            continue
          elif 'errorCode' in result and result['errorCode'] in warningErrorCode:
            warn = '{}: {}'.format(result['errorCode'], result['message'])
            print('  {}'.format(warn))
            logger.warn('{}'.format(warn))
            logger.warn('unitError: {}'.format(result['unitError']))
            if not len(result['orderModel']):
              continue

          total_output += self.writeOutput(config['api'], output_file,
                                           output_columns, result, index == 0)
          cwnum = self.writeCouponDetail(config['api'], coupon_file,
                                         output_columns, result, writeCouponHeader)
          if cwnum > 0:
            writeCouponHeader = False
          index += 1
  
    except Exception as e:
      print('  {}'.format(e))
      logger.error(e)
      logger.error(traceback.format_exc())
  
    logger.info('end')


