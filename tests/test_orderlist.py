import sys, os
myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + '/../')
sys.path.insert(0, myPath + '/../src')
import io
import configparser
import unittest
from OrderList import OrderList
from datetime import datetime
import pytz
from httpretty import HTTPretty, httprettified
import sure
import httpretty
import requests
import json
 
class TestOrderList(unittest.TestCase):

  SAMPLE_DATA_RPAY_SEARCH = {
    "orderNumberList": [
      "26161-20180101-22222201",
      "26161-20180101-22222202",
      "26161-20180101-22222203"
    ],
    "MessageModelList": [
      {
	"messageType": "INFO",
	"messageCode": "ORDER_EXT_API_SEARCH_ORDER_INFO_102",
	"message": "注文検索に成功しました。"
      }
    ],
    "PaginationResponseModel": {
      "totalRecordsAmount": None,
      "totalPages": None,
      "requestPages": None
    }
  }

  def load_json_file(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data

  SAMPLE_DATA_RPAY = load_json_file('tests/order_data_rpay.json')

  SAMPLE_DATA = load_json_file('tests/order_data.json')

  def test_genFileName(self):
    ol = OrderList()
    print('{}'.format(ol.genFileName('order')))
    print('{}'.format(ol.genFileName('coupon')))
    print('{}'.format(ol.genFileName('childOrder')))

  def test_extendOrder(self):
    ol = OrderList()
    for order in self.SAMPLE_DATA_RPAY['OrderModelList']:
      if len(order['PackageModelList'][0]['ItemModelList']) <= 1:
        continue
      eorder = ol.extendOrder(order)
      assert eorder is not None

  def test_grabChildren(self):
    ol = OrderList()
    d = {
      'aaa': {
        'bbb': 1,
        'ccc': 2,
        'ddd': {
          'eee': True
        },
        'fff': [1, 2, 3]
      }
    }
    ret = ol.grabChildren(d)
    self.assertEqual(ret['aaa.bbb'], 1)
    self.assertEqual(ret['aaa.ccc'], 2)
    self.assertEqual(ret['aaa.ddd.eee'], True)
    self.assertIsInstance(ret['aaa.fff'], list)
    print(ret)

  @httpretty.activate
  def test_rpayOrder_400(self):
    ol = OrderList()
    conf = ol.emptyConfig()
    ol.defaultConfig(conf)
    conf['api']['licenseKey'] = 'AAA'
    conf['api']['secretService'] = 'BBB'
    conf['api']['shopUrl'] = 'testshop_666'
    conf['api']['RPay'] = '1'
    ws = ol.getRmsService(conf['api'])
    (input_dict, output_columns, general_conf) = ol.readInput(conf, 'tests/input_test1.conf')

    post_searchOrder_response = """{
    "MessageModelList": [
	{
	    "messageType": "ERROR",
	    "messageCode": "ORDER_EXT_API_GET_ORDER_ERROR_009",
	    "message": "orderNumberListの項目を指定してください。"
	}
    ],
    "OrderModelList": []
}"""

    httpretty.register_uri(httpretty.POST, 'https://api.rms.rakuten.co.jp/es/2.0/order/searchOrder',
                           body=post_searchOrder_response,
                           content_type='application/json')

    result = ol.getOrderRPay(ws, input_dict, conf['api'])
    print(result.status)
    assert result['errorCode'] == 'W00-000'


  @httpretty.activate
  def test_rpayOrder_404(self):
    ol = OrderList()
    conf = ol.emptyConfig()
    ol.defaultConfig(conf)
    conf['api']['licenseKey'] = 'AAA'
    conf['api']['serviceSecret'] = 'BBB'
    conf['api']['shopUrl'] = 'testshop_666'
    conf['api']['RPay'] = '1'
    ws = ol.getRmsService(conf['api'])
    (input_dict, output_columns, general_conf) = ol.readInput(conf, 'tests/input_test1.conf')
    post_searchOrder_response = """{
    "orderNumberList": [
    ],
    "MessageModelList": [
	{
	    "messageType": "INFO",
	    "messageCode": "ORDER_EXT_API_SEARCH_ORDER_INFO_102",
	    "message": "注文検索に成功しました。"
	}
    ],
    "PaginationResponseModel": {
        "totalRecordsAmount": null,
        "totalPages": null,
        "requestPages": null
    }
}"""

    post_getOrder_response = """{
    "MessageModelList": [
	{
	    "messageType": "INFO",
	    "messageCode": "ORDER_EXT_API_GET_ORDER_INFO_102",
	    "message": "受注情報が取得できませんでした。",
	    "orderNumber": "234323-20180101-10101001"
	},
	{
	    "messageType": "INFO",
	    "messageCode": "ORDER_EXT_API_GET_ORDER_INFO_102",
	    "message": "受注情報が取得できませんでした。",
	    "orderNumber": "234323-20180101-10101002"
	},
	{
	    "messageType": "INFO",
	    "messageCode": "ORDER_EXT_API_GET_ORDER_INFO_102",
	    "message": "受注情報が取得できませんでした。",
	    "orderNumber": "234323-20180101-10101003"
	}
    ],
    "OrderModelList": []
}"""

    httpretty.register_uri(httpretty.POST,
                           'https://api.rms.rakuten.co.jp/es/2.0/order/searchOrder',
                           body=post_searchOrder_response,
                           content_type='application/json')

    result = ol.getOrderRPay(ws, input_dict, conf['api'])
    print(result.status)
    assert result['errorCode'] == 'W00-000'
    assert result['message'] == 'Not Found'
    assert len(result['orderModel']) == 0

  @httpretty.activate
  def test_rpayOrder_200(self):
    ol = OrderList()
    conf = ol.emptyConfig()
    ol.defaultConfig(conf)
    conf['api']['licenseKey'] = 'AAA'
    conf['api']['secretService'] = 'BBB'
    conf['api']['shopUrl'] = 'testshop_666'
    conf['api']['RPay'] = '1'
    conf['api']['getOrderVersion'] = '3'
    ws = ol.getRmsService(conf['api'])
    (input_dict, output_columns, general_conf) = ol.readInput(conf, 'tests/input_test1_rpay.conf')
    start = input_dict['getOrderRequestModel']['orderSearchModel']['startDate']
    end = input_dict['getOrderRequestModel']['orderSearchModel']['endDate']
    duration_1call = -1
    val = general_conf['duration']
    if val: duration_1call = int(val)
  
    datetimeList = ol.datetimeSplit(start, end, duration_1call)


    post_searchOrder_response = json.dumps(self.SAMPLE_DATA_RPAY_SEARCH)
    post_getOrder_response = json.dumps(self.SAMPLE_DATA_RPAY)

    httpretty.reset()
    httpretty.register_uri(httpretty.POST,
                           'https://api.rms.rakuten.co.jp/es/2.0/order/searchOrder',
                           body=post_searchOrder_response,
                           content_type='application/json')

    httpretty.register_uri(httpretty.POST,
                           'https://api.rms.rakuten.co.jp/es/2.0/order/getOrder',
                           body=post_getOrder_response,
                           content_type='application/json')

    result = ol.getOrderRPay(ws, input_dict, conf['api'])
    if not 'orderSearchModel' in input_dict['getOrderRequestModel']:
      input_dict['getOrderRequestModel']['orderSearchModel'] = {}
    input_dict['getOrderRequestModel']['orderSearchModel']['startDate'] = 0
    input_dict['getOrderRequestModel']['orderSearchModel']['endDate'] = 0

    assert result['errorCode'] == 'N00-000'

    outfile = ol.genFileName('order', 'data')
    couponfile = ol.genFileName('coupon', 'data')
    shippingfile = ol.genFileName('shipping', 'data')
    writeCouponHeader = True
    with io.open(outfile, "w", encoding=conf['api']['output_encoding']) as output_file:
      coupon_file = io.open(couponfile, "w", 
                            encoding=conf['api']['output_encoding'], 
                            errors='replace')
      ret = ol.writeOutput(conf['api'], output_file, output_columns, result, True)
      cwnum = ol.writeCouponDetail(conf['api'], coupon_file,
                                   output_columns, result, writeCouponHeader)

      shipping_file = io.open(shippingfile, "w", 
                              encoding=conf['api']['output_encoding'], 
                              errors='replace')
      cwnum = ol.writeShippingDetail(conf['api'], shipping_file,
                                     output_columns, result, True)
      #print(ret)

  def test_readInput(self):
    ol = OrderList()
    conf = ol.emptyConfig()
    ol.defaultConfig(conf)
    nhash, outputColumns, general_conf  = ol.readInput(conf, 'tests/input_test1.conf')

    print(nhash)
    osm = nhash['getOrderRequestModel']['orderSearchModel']
    csm = nhash['getOrderRequestModel']['orderSearchModel']['cardSearchModel']
    self.assertEqual(len(osm['pointStatus']), 2)
    self.assertEqual(osm['pointStatus'][0], '-1')
    self.assertEqual(osm['pointStatus'][1], '0')
    self.assertEqual(len(csm['cardStatus']), 1)
    self.assertEqual(csm['cardStatus'][0], '1')
    self.assertEqual(len(csm['payType']), 1)
    self.assertEqual(csm['payType'][0], '1')

  def test_readInput2(self):
    ol = OrderList()
    conf = ol.emptyConfig()
    ol.defaultConfig(conf)
    nhash, outputColumns, general_conf  = ol.readInput(conf, 'tests/input_test2.conf')

    orm = nhash['getOrderRequestModel']
    osm = nhash['getOrderRequestModel']['orderSearchModel']
    csm = nhash['getOrderRequestModel']['orderSearchModel']['cardSearchModel']
    self.assertEqual(osm['asuraku'], False)
    self.assertEqual(len(orm['orderNumber']), 2)
    self.assertEqual(orm['orderNumber'][0], '666666-333333333-xxxxxxx')
    self.assertEqual(len(csm['cardStatus']), 2)
    self.assertEqual(csm['cardStatus'][0], '1')
    self.assertEqual(csm['cardStatus'][1], '3')
    self.assertEqual(len(csm['payType']), 1)
    self.assertEqual(csm['payType'][0], '1')

    self.assertIsInstance(osm['startDate'], datetime)
    self.assertIsInstance(osm['endDate'], datetime)

  def test_datetimeSplit(self):
    ol = OrderList()
    ret = ol.datetimeSplit(
      datetime.strptime('2016/01/01 00:00:00', '%Y/%m/%d %H:%M:%S'),
      datetime.strptime('2016/01/03 10:00:00', '%Y/%m/%d %H:%M:%S'), 86400)
    self.assertEqual(len(ret), 3)

    ret = ol.datetimeSplit(
      datetime.strptime('2016/01/01 00:00:00', '%Y/%m/%d %H:%M:%S'),
      datetime.strptime('2016/01/03 10:00:00', '%Y/%m/%d %H:%M:%S'), 3600)
    self.assertEqual(len(ret), 59)

    ret = ol.datetimeSplit(
      datetime.strptime('2016/01/01 00:00:00', '%Y/%m/%d %H:%M:%S'),
      datetime.strptime('2016/01/04 23:59:59', '%Y/%m/%d %H:%M:%S'), 3600)
    self.assertEqual(len(ret), 96)

    ret = ol.datetimeSplit(
      datetime.strptime('2016/01/01 00:00:00', '%Y/%m/%d %H:%M:%S'),
      datetime.strptime('2016/01/04 23:59:59', '%Y/%m/%d %H:%M:%S'), -1)
    self.assertEqual(len(ret), 1)


  def test_writeOutput(self):
    ol = OrderList()

    ret = self.SAMPLE_DATA

    outfile = ol.genFileName('order', 'data')
    conf = ol.emptyConfig()
    ol.defaultConfig(conf)
    #conf['api']['output_delimiter'] = ','
    #conf['api']['output_quotechar'] = '"'
    #conf['api']['output_encoding'] = 'cp932'
    input, output_columns, general_conf = ol.readInput(conf, 'input.txt')
    with io.open(outfile, "w", encoding=conf['api']['output_encoding']) as output_file:
      ret = ol.writeOutput(conf['api'], output_file, output_columns, ret, True)
      print(ret)

  @httpretty.activate
  def test_writeOutputRpay(self):
    ol = OrderList()

    post_searchOrder_response = json.dumps(self.SAMPLE_DATA_RPAY_SEARCH)
    post_getOrder_response = json.dumps(self.SAMPLE_DATA_RPAY)

    conf = ol.emptyConfig()
    ol.defaultConfig(conf)
    conf['api']['licenseKey'] = 'AAA'
    conf['api']['secretService'] = 'BBB'
    conf['api']['shopUrl'] = 'testshop_666'
    conf['api']['RPay'] = '1'
    conf['api']['getOrderVersion'] = '3'
    ws = ol.getRmsService(conf['api'])
    (input_dict, output_columns, general_conf) = ol.readInput(conf, 'tests/input_test1_rpay.conf')

    httpretty.reset()
    httpretty.register_uri(httpretty.POST,
                           'https://api.rms.rakuten.co.jp/es/2.0/order/searchOrder',
                           body=post_searchOrder_response,
                           content_type='application/json')

    httpretty.register_uri(httpretty.POST,
                           'https://api.rms.rakuten.co.jp/es/2.0/order/getOrder',
                           body=post_getOrder_response,
                           content_type='application/json')

    ret = ol.getOrderRPay(ws, input_dict, conf['api'])

    outfile = ol.genFileName('order', 'data')
    conf = ol.emptyConfig()
    ol.defaultConfig(conf)
    #conf['api']['output_delimiter'] = ','
    #conf['api']['output_quotechar'] = '"'
    #conf['api']['output_encoding'] = 'cp932'
    input, output_columns, general_conf = ol.readInput(conf, 'input_rpay.txt')
    with io.open(outfile, "w", encoding=conf['api']['output_encoding']) as output_file:
      ret = ol.writeOutput(conf['api'], output_file, output_columns, ret, True)
      print(ret)


