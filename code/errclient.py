import sys
import traceback

# test.py
def application(env, start_response):


    try:
        # Send our initial 200 response
        start_response('200 OK', [('Content-Type','text/html')])
        
        # Throw our example exception
        raise Exception("Something terrible has happened.")

        # Send the environment to the client
        iterable_resp = [(">> %s: %s\n" % r).encode() for r in env.items()]
        iterable_resp.sort()
        return iterable_resp

    except:
        exc_info = sys.exc_info()
        start_response(
            "500 Internal Server Error",
            [('Content-Type', 'text/plain')],
            exc_info=exc_info
        )

        # exc_info is a tuple of (type, value, traceback)
        exc_type, value, tb = exc_info
        exc = traceback.format_exception(exc_type, value, tb)

        return [ ''.join(exc).encode() ]

