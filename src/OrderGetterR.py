import os
from OrderList import OrderList

if __name__ == '__main__':
    ol = OrderList()
    ol.version = '1.1.4'
    ol.myname = 'OrderGetterR'
    if os.name == 'nt': ol.myname += '.exe' 
    ol.main()

