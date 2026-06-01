def get_data(url, t=30, r=3, j=True, h=None, cache=False, cb=None, opts={}, **kw):
    """Gets data from the url. t is the timeout, r is retries, j means parse json,
    h is headers, cache caches it, cb is a callback, opts are extra options.
    Returns the data, or None if it fails."""
    ...
