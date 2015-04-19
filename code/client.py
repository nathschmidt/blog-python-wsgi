# 
# client.py
# A very simple Python3 wsgi client application
#
def application(env, start_response):
	# Send our status code and headers
    start_response('200 OK', [('Content-Type','text/plain')])

    # Send the environment to the client
    iterable_resp = [(">> %s: %s\n" % r).encode() for r in env.items()]
    iterable_resp.sort()
    return iterable_resp

