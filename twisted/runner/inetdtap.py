# -*- test-case-name: twisted.runner.test.test_inetdtap -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted inetd TAP support

The purpose of inetdtap is to provide an inetd-like server, to allow Twisted to
invoke other programs to handle incoming sockets.
This is a useful thing as a "networking swiss army knife" tool, like netcat.

To use it, create a file named `sampleinetd.conf` with:

8123       stream  tcp  wait glyph  /bin/cat -

and a `rpc.conf` file with a blanc line in it.

You can then run it as and port 8123 properly became an echo server.

twistd -n inetd -f sampleinetd.conf -r rpc.conf


"""

import os, pwd, grp, socket

from twisted.runner import inetd, inetdconf
from twisted.python import log, usage
from twisted.python.deprecate import deprecated
from twisted.python.versions import Version
from twisted.internet.protocol import ServerFactory
from twisted.application import internet, service as appservice

# Protocol map
protocolDict = {'tcp': socket.IPPROTO_TCP, 'udp': socket.IPPROTO_UDP}


class Options(usage.Options):

    optParameters = [
        ['rpc', 'r', '/etc/rpc', 'DEPRECATED. RPC procedure table file'],
        ['file', 'f', '/etc/inetd.conf', 'Service configuration file']
    ]

    optFlags = [['nointernal', 'i', "Don't run internal services"]]

    compData = usage.Completions(
        optActions={"file": usage.CompleteFiles('*.conf')}
        )



class RPCServer(internet.TCPServer):
    """
    DEPRECATED.
    """

    @deprecated(Version("Twisted", 16, 0, 0))
    def __init__(self, rpcVersions, rpcConf, proto, service):
        pass



def makeService(config):
    s = appservice.MultiService()
    conf = inetdconf.InetdConf()
    conf.parseFile(open(config['file']))

    for service in conf.services:
        protocol = service.protocol

        if service.protocol.startswith('rpc/'):
            log.msg('Skipping rpc service due to lack of rpc support')
            continue

        if (protocol, service.socketType) not in [('tcp', 'stream'),
                                                  ('udp', 'dgram')]:
            log.msg('Skipping unsupported type/protocol: %s/%s'
                    % (service.socketType, service.protocol))
            continue

        # Convert the username into a uid (if necessary)
        try:
            service.user = int(service.user)
        except ValueError:
            try:
                service.user = pwd.getpwnam(service.user)[2]
            except KeyError:
                log.msg('Unknown user: ' + service.user)
                continue

        # Convert the group name into a gid (if necessary)
        if service.group is None:
            # If no group was specified, use the user's primary group
            service.group = pwd.getpwuid(service.user)[3]
        else:
            try:
                service.group = int(service.group)
            except ValueError:
                try:
                    service.group = grp.getgrnam(service.group)[2]
                except KeyError:
                    log.msg('Unknown group: ' + service.group)
                    continue

        if service.program == 'internal':
            if config['nointernal']:
                continue

            # Internal services can use a standard ServerFactory
            if not inetd.internalProtocols.has_key(service.name):
                log.msg('Unknown internal service: ' + service.name)
                continue
            factory = ServerFactory()
            factory.protocol = inetd.internalProtocols[service.name]
        else:
            factory = inetd.InetdFactory(service)

        if protocol == 'tcp':
            internet.TCPServer(service.port, factory).setServiceParent(s)
        elif protocol == 'udp':
            raise RuntimeError("not supporting UDP")
    return s
