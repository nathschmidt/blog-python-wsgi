#! /usr/bin/env python3

#
# Python3 WSGI Server Example
# 

import sys
import asyncio
import importlib
from io import StringIO

from datetime import datetime
from copy import copy
from urllib.parse import urlparse

# 
# Defaults and keys for the environment object
# 
_ENV_DEFAULTS = {
        # PEP 3333 required WSGI vars
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': 'http',
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
        'wsgi.errors': sys.stderr,
        'wsgi.input': None,

        # CGI Vars
        'REQUEST_METHOD': None,
        'SCRIPT_NAME': None,
        'PATH_INFO': None,
        'QUERY_STRING': None,
        'SERVER_NAME': None,
        'SERVER_PORT': None,
        'HTTP_HOST': None,
        'SERVER_PROTOCOL': None
}

class WsgiServer(asyncio.Protocol):
    '''
        WSGI Server Example
    '''

    application = None

    def __init__(self):
        self.transport = None
        self.request = {
            "method": None,
            "path": None,
            "version": None
        }
        self.env = {}
        self.raw_request = ""
        self.response = None
        self._response_started = False


    def connection_made(self, transport):
        '''
            Handle for when a new connection is made.
        '''
        self.transport = transport


    def data_received(self, data):
        '''
            Fired when any data is recieved
        '''
        text = data.decode("utf-8") 

        self.raw_request = text
        self._parse_request(text)
        self.env = self._get_env()

        self.wsgi()


    def wsgi(self):
        '''
            The heart of the WSGI Server side interface
        '''
        # The heart of our Server-side WSGI
        result = WsgiServer.application(self.env, self.start_response)
        # Our result makes up the body of the request.
        # It's an iterable of byte streams (in py3)

        # Begin formating our response
        status_line = "%(httpver)s %(status)s\r\n" % self.response
        response = status_line.encode()

        # Format our headers
        for header in self.response['headers']:
            header_line = '%s: %s\r\n' % header
            response += header_line.encode()

        response += b'\r\n'

        # Prepare our response body
        for data in result:
            response += data

        # Write the response to the client
        self.transport.write(response)

        self.transport.close()


    def start_response(self, status, response_headers, exc_info=None):
        '''
            The start response callback function handed to 
            the wsgi application.
        '''

        # Eg. Format: Tue, 31 Mar 2015 12:54:48 GMT
        today = datetime.now()
        datestr = today.strftime('%a, %d %m %b %Y %H:%M:%S %z')

        # add some essential headers
        # We'll elect to take care of just these headers
        headers = [
            # Properly formatted header tuples
            ('Date', datestr),
            ('Server', 'asyncio-wsgi-example-server'),
        ]

        headers += response_headers

        if self._response_started and exc_info is None:
            raise Exception('start_response callback already fired')

        elif exc_info is not None:
            # Clear out any previous status and headers.
            self.response['status']  = status
            self.response['headers'] = headers
            return

        self._response_started = True

        self.response = {
            "httpver": self.request['version'],
            "status": status,
            "headers": headers
        }


    def _parse_request(self, text):
        '''
            Parse an incomming HTTP Request

            Note: This server doesn't care about post data,
            or form data
        '''
        # Grab the request line
        request_line = text.splitlines()[0]
        request_line = request_line.strip()

        meth, path, vers = request_line.split()

        self.request["method"] = meth
        self.request["path"] = path
        self.request["version"] = vers


    def _get_env(self):
        '''
            Get our environment from the request.

            This is far from a complete environment, it 
            doesn't fill out the required HTTP_ variables
            but, it does conform, if loosely, to the spec.
        '''
        env = copy(_ENV_DEFAULTS)
        urlbits = urlparse(self.request['path'])

        env['wsgi.input'] = StringIO(self.raw_request)
        env['REQUEST_METHOD'] = self.request['method']
        env['SCRIPT_NAME'] = self.request['path']
        env['PATH_INFO'] = ''
        env['QUERY_STRING'] = urlbits.query
        env['SERVER_PROTOCOL'] = self.request['version']

        return env


def main():
    HOST = 'localhost'
    PORT = 8888

    # Parse our arguments
    # we want two arguments, 
    #   1) a module to load up, 
    #   2) a function in that module to use.
    # Anything else, display usage
    args = sys.argv[1:] # cut off the extra first arg
    if len(args) < 2:
        print("Usage: server.py <module> <wsgi app func>")
        exit(0)

    module = args[0]
    app_name = args[1]

    target_module = __import__(module)
    app_func = getattr(target_module, app_name)

    # Set our application
    WsgiServer.application = app_func

    loop = asyncio.get_event_loop()

    coro = loop.create_server(WsgiServer, HOST, PORT)
    
    server = loop.run_until_complete(coro)

    _ENV_DEFAULTS['SERVER_NAME'] = HOST
    _ENV_DEFAULTS['SERVER_PORT'] = PORT
    _ENV_DEFAULTS['HTTP_HOST'] = "http://%s:%s" % (HOST, PORT)

    print('Serving on {}'.format(server.sockets[0].getsockname()))

    try:
        loop.run_forever()

    except KeyboardInterrupt:
        pass

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()

if __name__ == '__main__':
    main()

