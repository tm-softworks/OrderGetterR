### 受注ゲッターＲ(OrderGetterR)

受注ゲッターＲ は、受注APIを利用し受注情報の一覧をCSVファイルに出力するツールです。

### ファイル構成

 - OrderGetterR.exe
   Mac版は、OrderGetterR。
 - readme.txt
 - input.txt
   検索条件、出力項目を設定します。
   設定方法については、マニュアルを参照下さい。
   マニュアル： https://product.tm-softworks.net/OrderGetterR/
 - input_type1.txt
   一般的に利用される項目を出力するように設定したファイルです。
 - setting.ini
   受注情報出力先
   受注APIの認証情報（ライセンスキー、シークレットキー）等を設定します

### 使用方法

 1. setting.ini に、ライセンスキー、シークレットキーを設定する
    ※ RMSにて申請する必要があります。

 2. 取得したい受注情報の条件、出力情報をinput.txt に記載する

 3. コマンドプロンプト (Macの場合は、Terminal)にて実行する
    Windowsの場合
      OrderGetterR.exe input.txt

    MacOSの場合	
      ./OrderGetterR input.txt

  詳細は、以下のページをご参照下さい。
    https://product.tm-softworks.net/OrderGetterR/


###### 3rd party license

 受注ゲッターＲは、以下の3rd partyライブラリを利用しています。
 
 - Python Rakuten Web Service (version: 0.2.1)
 Copyright (c) 2016, Salem Harrache
 https://github.com/alexandriagroup/rakuten-ws/blob/master/LICENSE

 - pytz - World Timezone Definitions for Python (2016.10)
 Copyright (c) 2003-2005 Stuart Bishop <stuart@stuartbishop.net>
 https://github.com/newvem/pytz/blob/master/LICENSE.txt
 
 - Zeep: Python SOAP client (version: 1.1.0)
 Copyright (c) 2016-2017 Michael van Tellingen
 https://github.com/mvantellingen/python-zeep/blob/master/LICENSE
 
