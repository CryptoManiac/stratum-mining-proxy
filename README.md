stratum-mining-proxy
====================

Application providing bridge between old HTTP/getwork protocol and Stratum mining protocol

Installation on Windows
-----------------------

1. Download official Windows binaries (EXE) from http://pool.itzod.ru/mining_proxy.exe or http://ltcmine.ru/mining_proxy.exe
2. Open downloaded file. It will open console window. Using default settings, proxy connects to Itzod's mining pool (or ltcmine pool, if -pa scrypt was specified)
3. If you want to connect to another pool or change other proxy settings, type "mining_proxy.exe --help" in console window.

Installation using Github
-------------------------
This is advanced option for experienced users, but give you the easiest way for updating the proxy.

1. git clone https://github.com/CryptoManiac/stratum-mining-proxy.git
2. cd stratum-mining-proxy
3. sudo apt-get install python-dev # Development package of Python are necessary
4. sudo python distribute_setup.py # This will upgrade setuptools package
5. sudo python setup.py develop # This will install required dependencies (namely Twisted and Stratum libraries),
but don't install the package into the system.
6. You can start the proxy by typing "./mining_proxy.py" in the terminal window. Using default settings, Itzod's mining pool (or ltcmine pool, if -pa scrypt was specified)
7. If you want to connect to another pool or change other proxy settings, type "./mining_proxy.py --help".
8. If you want to update the proxy, type "git pull" in the package directory.

Compiling midstate C extension
------------------------------
For some really big operations using getwork interface of this proxy, you'll find
useful "midstatec" C extension, which significantly speeds up midstate calculations
(yes, plain python implementation is *so* slow). For enabling this extension,
just type "make" in midstatec directory. Proxy will auto-detect compiled extension
on next startup.

Contact
-------

This proxy is provided by Slush's mining pool at http://mining.bitcoin.cz. You can contact the author
by email info(at)bitcoin.cz or by IRC on irc.freenode.net in channel #stratum.

This proxy was modified by LTCMine.ru and pool.itzod.ru minings pools administrator, you can ask your 
questions by email balthazar(at)yandex.ru or PM at btc-e.com exchange.
