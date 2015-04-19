This is part 1 of a series of blog posts about WSGI, Websockets, HTTP2, and what using python on the web is going to look like in the future. This section is a breakdown of the WSGI specification, how it works and what it looks like.

## What is WSGI?

WSGI stands for Web Server Gateway Interface. Which is a fancy way of saying it is the correct method of writing web facing applications or frameworks in python. Since it's creation and release in Sept. of 2010, WSGI has taken off, with almost all of the major web application frameworks adopting it.

The required client-side of the interface is very simple. The module exposes a target `application` callable, which can be just a standard function call, which takes two positional arguments, the first is a dictionary describing the environment and request information, the second is a callback function to handle the status and any headers for the response. The returned result of our application function is the response body, which should be an iterable of byte strings.

The server side of things is slightly more complex, but fundamentally simple. Essentially, the server creates our environment dict, based off the request, and calls the application function. Once the application function has run and compeleted, the response is generated and sent to the client.

The rest of this post is the breakdown of how exactly each side of the interface goes about doing what it is supposed to, as well as an overall look into how WSGI works.

## Onto the code

All of this code is available in full from my [github account][1], some of the examples below have been condensed for brevity.

### The Client

A very simple WSGI client might look something like this:

    # client.py
    # A very simple Python3 wsgi client application
    #
    def application(env, start_response):
        # Send our status code and headers
        start_response('200 OK', [('Content-Type','text/plain')])
    
        # Send the environment to the client
        return [(">> %s: %s\n" % r).encode() for r in env.items()]
    

All this client does is accept a wsgi request and return the environment that was handed to it. Nothing fancy. It's very simple. Your favourite web application framework (Django, Flask, Pyramid etc.) will handle this entry point, then also provide a mechanism for routing requests, extracting data from requests, and crafting an understandable and correct HTTP response. Afterall we use frameworks to make our lives easier, so it does make sense that they'd want to do all these things for us. However, it's always good to understand what is going on under the hood.

If you fire up a WSGI server and checkout the output of this client, it might be easy to see how a basic route system could be setup, based on the information that comes in from the environment.

### The Server

Full code for the server is here [github account][1], but the important parts are below.

The server uses the Python3 asyncio module to handle the actual TCP connections, and reading from/writing to the client. So we can then focus on the implementation of WSGI, rather than worrying too much about our tcp situation.

    class WsgiServer(asyncio.Protocol):
    
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
    
                Note: This server doesnt care about post data,
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
                doesnt fill out the required HTTP_ variables
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
    

That is essentially all we really need in order to understand what's happening. To break it down a bit, the `wsgi` function is the heart of running the core `application` function, we give it the details it needs to make some decisions, set our status code and headers, then take it's result and return that to the client.

## The Design of WSGI

WSGI is the product of [PEP 3333][2] proposing "a simple and universal interface between web servers and web applications or frameworks", and goes on to document how the WSGI interface works, how it should behave, what data should be available to the application, and how the application can create the response for the client.

The "Rationale and Goals" section of the PEP is quite interesting, it references Java's servlet API as a point of inspiration and, quite rightly, points out that at the time (September 2010) developing web application in python was a massive headache to get started with and make the best choices without backing yourself into a nasty corner.

The core of WSGI is incredibly simple. It was even one of the main goals of the specification, "since no existing servers or frameworks support WSGI ... WSGI must be easy to implement", this was to ensure that the overheads of adding WSGI to the existing systems at the time were as low as possible.

### The Environment

The environment is a dict of CGI and WSGI variables. It's all the juciey and important details of the request, the variables that allow us to implement route based redirection, read data from forms and post requests, as well as all the headers from the client.  Outside of the actual CGI variables there's not much else that's interesting about the environment, there are some specified WSGI variables that must be present or accounted for, but primarily the environment is the familiar set of `HOST_NAME`, `REQUEST_METHOD` etc. collection of CGI variables.

### The Callback

In python we can take any class and add function-esk behaviour to it simply by defining the behaviour to take place when that object is treated like a function. Bit easier to explain in code:

    class Foo(object):
    
        def __call__(self, *args):
            print " ".join(args)
    
    >>> foo = Foo
    >>> foo("Some". "list of", "arguments.")
    Some list of arguments.
    

The WSGI PEP takes this into account when it defines the rules around what can happen with regard to the callable. The PEP explicitly states we can't care about the details of the callable, as far as our application is concerned it is *only* callable; we can't depend on any other behaviour, method, or data.

Ok, that said, onto the nice meaty parts of the Callback.

The callback is officially called `start_response`, it accepts 2 positional arguments, `status` and `response_headers`, and a keyword argument, `exc_info`. To quote the spec:

*   `status` - is a HTTP status string. eg. "200 OK", "404 Not Found".
*   `response_headers` - is a list of tuples of the form (`header_name`, `header_value`).
*   `exc_info` - Exception information if something has gone wrong, defaults to `None`.

`status` is by far the simplest of all the arguements, it is simply a valid HTTP status string as per [RFC 2616][3]. Really it just has to be a status code and reason separated by a single space. Anything other than that may be rejected by the server. Very flexible and simple way of communicating if the request has succeeded or failed, a decision that is of course left up to the application.

The `response_headers` arguement is slightly more complicated (though still very simple), it's only real requirementthat it is a list, containing tuples of `header_name` and `header_value`. Of course, as they are tuples the order is important. Just like the `status` argument the `header_value` field for each header shouldn't contain any control characters or other strangeness. `header_name` must be a valid HTTP header field-name, also defined in [RFC 2616][3].

Things will start to get interesting for us though, if we try and set a `Date` header, for instance. The spec actually allows the server to do whatever it wants to do to the out going header fields, meaning it's perfectly within its rights to say, override our custom `Date` header value with a more accurate header value. In practice probably not a great idea to try setting the `Date` header regardless, it is definitely something the outgoing machine should serice. It's a good example of the behaviour though, and a bit of a warning why you should never assume your client will definitely get unmolested headers.

The final argument to our response is the `exc_info` named parameter, for when things go pear shaped. The designers of the WSGI realized that setting the headers and returning some result are disconnected from each other. Meaning it's entirely possible for an application to set the headers and status field before generating the response. So, what if our application set the headers and status field, but then later down the line raises an exception. There are an infinite number of conditions that could cause something like this to happen, eg a database connection fails, a catastrophic event should definitely change the way a response is returned to the client. For example, Instead of a 2xx status code, they should probably see a 5xx or 4xx status code.

So our server has to be able to handle our `start_response` function being called more than once, so long as the `exc_info` argument is present, our server will happily overwrite the previously specified headers and status, our returned result is treated as the body for the request. So, our application shouldn't just let exceptions propagate to the server, we need to catch them in our application and display or return something helpful. What helpful means is entirely up to the application.

### The Response

The body of the response is formed from the returned value of the `application`. As with the callback function, so long as the application is callable (i.e. has a `__call__` method) it can be used. The return value is expected to be an iterable, with each value from the iteration added to the body of the response. Eg:

    # Prepare our response body
    for data in result:
        response += data
    
    # Write the response to the client
    self.transport.write(response)
    

More complex servers don't worry too much about this rule, but, particlarly in Python3's case, the values of the iterable are expected to be byte array's. This is because HTTP is primarily concerned with bytes rather than unicode text. Now on to the final question, why does the response have to be iterable? Because iterables are incredibly flexible, and the common interface for strings, files, lists, etc. So you can very easily wrap all manor of behaviour up in an iterator.

## Summary

So, that's what WSGI is, a well thought out, request-response based interface for using python on the web. But, how well, I wonder, does it handle asyncronous connections like WebSockets?  That's the question I aim to explore in my next post, and ultimately the subject of this series.

 [1]: http://github.com/nathschmidt/blog-python-wsgi
 [2]: https://www.python.org/dev/peps/pep-3333/
 [3]: https://www.ietf.org/rfc/rfc2616.txt