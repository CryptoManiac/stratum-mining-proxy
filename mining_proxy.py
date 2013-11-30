#!/usr/bin/env python
'''
    Stratum mining proxy
    Copyright (C) 2012 Marek Palatinus <info@bitcoin.cz>
    
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import argparse
import time
import os

def parse_args():
    parser = argparse.ArgumentParser(description='This proxy allows you to run getwork-based miners against Stratum mining pool.')
    parser.add_argument('-o', '--host', dest='host', type=str, default='pool.itzod.ru', help='Hostname of Stratum mining pool')
    parser.add_argument('-p', '--port', dest='port', type=int, default=3333, help='Port of Stratum mining pool')
    parser.add_argument('-sh', '--stratum-host', dest='stratum_host', type=str, default='0.0.0.0', help='On which network interface listen for stratum miners. Use "localhost" for listening on internal IP only.')
    parser.add_argument('-sp', '--stratum-port', dest='stratum_port', type=int, default=3333, help='Port on which port listen for stratum miners.')
    parser.add_argument('-oh', '--getwork-host', dest='getwork_host', type=str, default='0.0.0.0', help='On which network interface listen for getwork miners. Use "localhost" for listening on internal IP only.')
    parser.add_argument('-gp', '--getwork-port', dest='getwork_port', type=int, default=8332, help='Port on which port listen for getwork miners. Use another port if you have bitcoind RPC running on this machine already.')
    parser.add_argument('-nm', '--no-midstate', dest='no_midstate', action='store_true', help="Don't compute midstate for getwork. This has outstanding performance boost, but some old miners like Diablo don't work without midstate.")
    parser.add_argument('-rt', '--real-target', dest='real_target', action='store_true', help="Propagate >diff1 target to getwork miners. Some miners work incorrectly with higher difficulty.")
    parser.add_argument('-cl', '--custom-lp', dest='custom_lp', type=str, help='Override URL provided in X-Long-Polling header')
    parser.add_argument('-cs', '--custom-stratum', dest='custom_stratum', type=str, help='Override URL provided in X-Stratum header')
    parser.add_argument('-cu', '--custom-user', dest='custom_user', type=str, help='Use this username for submitting shares')
    parser.add_argument('-cp', '--custom-password', dest='custom_password', type=str, help='Use this password for submitting shares')    
    parser.add_argument('--blocknotify', dest='blocknotify_cmd', type=str, default='', help='Execute command when the best block changes (%%s in BLOCKNOTIFY_CMD is replaced by block hash)')
    parser.add_argument('--socks', dest='proxy', type=str, default='', help='Use socks5 proxy for upstream Stratum connection, specify as host:port')
    parser.add_argument('--tor', dest='tor', action='store_true', help='Configure proxy to mine over Tor (requires Tor running on local machine)')
    parser.add_argument('-t', '--test', dest='test', action='store_true', help='Run performance test on startup')    
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='Enable low-level debugging messages')
    parser.add_argument('-q', '--quiet', dest='quiet', action='store_true', help='Make output more quiet')
    parser.add_argument('-i', '--pid-file', dest='pid_file', type=str, help='Store process pid to the file')
    parser.add_argument('-pa', '--pow-algo', dest='pow_algo', default='doublesha', type=str, help='Proof of work function')
    return parser.parse_args()

from stratum import settings
settings.LOGLEVEL='INFO'

if __name__ == '__main__':
    # We need to parse args & setup Stratum environment
    # before any other imports
    args = parse_args()
    if args.quiet:
        settings.DEBUG = False
        settings.LOGLEVEL = 'WARNING'
    elif args.verbose:
        settings.DEBUG = True
        settings.LOGLEVEL = 'DEBUG'
            
from twisted.internet import reactor, defer
from stratum.socket_transport import SocketTransportFactory, SocketTransportClientFactory
from stratum.services import ServiceEventHandler
from twisted.web.server import Site

from mining_libs import stratum_listener
from mining_libs import getwork_listener
from mining_libs import client_service
from mining_libs import jobs
from mining_libs import worker_registry
from mining_libs import multicast_responder
from mining_libs import version
from mining_libs import utils

import stratum.logger
log = stratum.logger.get_logger('proxy')

def on_shutdown(f):
    '''Clean environment properly'''
    log.info("Shutting down proxy...")
    f.is_reconnecting = False # Don't let stratum factory to reconnect again
    
@defer.inlineCallbacks
def on_connect(f, workers, job_registry):
    '''Callback when proxy get connected to the pool'''
    log.info("Connected to Stratum pool at %s:%d" % f.main_host)
    #reactor.callLater(30, f.client.transport.loseConnection)
    
    # Hook to on_connect again
    f.on_connect.addCallback(on_connect, workers, job_registry)
    
    # Every worker have to re-autorize
    workers.clear_authorizations() 
    
    if args.custom_user:
        log.info("Authorizing custom user %s, password %s" % (args.custom_user, args.custom_password))
        workers.authorize(args.custom_user, args.custom_password)
        
    # Subscribe for receiving jobs
    log.info("Subscribing for mining jobs")
    (_, extranonce1, extranonce2_size) = (yield f.rpc('mining.subscribe', []))
    job_registry.set_extranonce(extranonce1, extranonce2_size)
    stratum_listener.StratumProxyService._set_extranonce(extranonce1, extranonce2_size)
    
    defer.returnValue(f)
     
def on_disconnect(f, workers, job_registry):
    '''Callback when proxy get disconnected from the pool'''
    log.info("Disconnected from Stratum pool at %s:%d" % f.main_host)
    f.on_disconnect.addCallback(on_disconnect, workers, job_registry)
    
    stratum_listener.MiningSubscription.disconnect_all()
    
    # Reject miners because we don't give a *job :-)
    workers.clear_authorizations() 
    
    return f              

def test_launcher(result, job_registry):
    def run_test():
        log.info("Running performance self-test...")
        for m in (True, False):
            log.info("Generating with midstate: %s" % m)
            log.info("Example getwork:")
            log.info(job_registry.getwork(no_midstate=not m))

            start = time.time()
            n = 10000
            
            for x in range(n):
                job_registry.getwork(no_midstate=not m)
                
            log.info("%d getworks generated in %.03f sec, %d gw/s" % \
                     (n, time.time() - start, n / (time.time()-start)))
            
        log.info("Test done")
    reactor.callLater(1, run_test)
    return result


@defer.inlineCallbacks
def main(args):
    if args.pid_file:
        fp = file(args.pid_file, 'w')
        fp.write(str(os.getpid()))
        fp.close()
    
    if args.port != 3333:
        '''User most likely provided host/port
        for getwork interface. Let's try to detect
        Stratum host/port of given getwork pool.'''
        
        try:
            new_host = (yield utils.detect_stratum(args.host, args.port))
        except:
            log.exception("Stratum host/port autodetection failed")
            new_host = None
            
        if new_host != None:
            args.host = new_host[0]
            args.port = new_host[1]

    log.info("Stratum proxy version: %s" % version.VERSION)
    
    if args.tor and args.host != 'pool.itzod.ru':
        log.info("Configuring Tor connection")
        args.proxy = '127.0.0.1:9050'
        args.host = 'pool57wkuu5yuhzb.onion'
        args.port = 3333
        
    if args.proxy:
        proxy = args.proxy.split(':')
        if len(proxy) < 2:
            proxy = (proxy, 9050)
        else:
            proxy = (proxy[0], int(proxy[1]))
        log.info("Using proxy %s:%d" % proxy)
    else:
        proxy = None
    
    if args.pow_algo == 'scrypt':
        args.real_target = True
        if args.host == 'pool.itzod.ru':
            args.host = 'ltcmine.ru'

	log.info("Trying to connect to Stratum pool at %s:%d" % (args.host, args.port))        

    # Connect to Stratum pool
    f = SocketTransportClientFactory(args.host, args.port,
                debug=args.verbose, proxy=proxy,
                event_handler=client_service.ClientMiningService)
	
    utils.set_hashing_algo(args.pow_algo)
    log.info("Setting PoW algo: %s" % args.pow_algo)
    
    job_registry = jobs.JobRegistry(f, cmd=args.blocknotify_cmd,
                   no_midstate=args.no_midstate, real_target=args.real_target)
    client_service.ClientMiningService.job_registry = job_registry
    client_service.ClientMiningService.reset_timeout()
    
    workers = worker_registry.WorkerRegistry(f)
    f.on_connect.addCallback(on_connect, workers, job_registry)
    f.on_disconnect.addCallback(on_disconnect, workers, job_registry)

    if args.test:
        f.on_connect.addCallback(test_launcher, job_registry)
    
    # Cleanup properly on shutdown
    reactor.addSystemEventTrigger('before', 'shutdown', on_shutdown, f)

    # Block until proxy connect to the pool
    yield f.on_connect
    
    # Setup getwork listener
    if args.getwork_port > 0:
        reactor.listenTCP(args.getwork_port, Site(getwork_listener.Root(job_registry, workers,
                                                    stratum_host=args.stratum_host, stratum_port=args.stratum_port,
                                                    custom_lp=args.custom_lp, custom_stratum=args.custom_stratum,
                                                    custom_user=args.custom_user, custom_password=args.custom_password)),
                                                    interface=args.getwork_host)
    
    # Setup stratum listener
    if args.stratum_port > 0:
        stratum_listener.StratumProxyService._set_upstream_factory(f)
        reactor.listenTCP(args.stratum_port, SocketTransportFactory(debug=False, event_handler=ServiceEventHandler))

    # Setup multicast responder
    reactor.listenMulticast(3333, multicast_responder.MulticastResponder((args.host, args.port), args.stratum_port, args.getwork_port), listenMultiple=True)
    
    log.info("-----------------------------------------------------------------------")
    if args.getwork_host == '0.0.0.0' and args.stratum_host == '0.0.0.0':
        log.info("PROXY IS LISTENING ON ALL IPs ON PORT %d (stratum) AND %d (getwork)" % (args.stratum_port, args.getwork_port))
    else:
        log.info("LISTENING FOR MINERS ON http://%s:%d (getwork) and stratum+tcp://%s:%d (stratum)" % \
                 (args.getwork_host, args.getwork_port, args.stratum_host, args.stratum_port))
    log.info("-----------------------------------------------------------------------")

if __name__ == '__main__':
    main(args)
    reactor.run()
