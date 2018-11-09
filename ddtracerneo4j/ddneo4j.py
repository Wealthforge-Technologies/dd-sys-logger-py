import wrapt
import ddsyslogger
from neo4j.v1    import GraphDatabase, Session
from ddtrace     import Pin
from ddtrace.ext import sql, net, db

SERVICE = 'neo4j'

def patch():
    if getattr(Session, '_datadog_patch', False):
        return

    setattr(Session, '_datadog_patch', True)

    wrapt.wrap_function_wrapper(GraphDatabase, 'driver', _driver)
    wrapt.wrap_function_wrapper(Session,       'run',    _run)

def parse_neo4j_dsn(args, kwargs):
    # EXAMPLES:
    #       ARGS
    #           bolt://10.0.0.1:8080
    #           bolt://10.0.0.1
    #
    #       KWARGS
    #           auth=(neo4j, abc123)
    host = args[0].split('bolt://')[1]
    arr  = host.split(':')
    if len(arr) == 1: # no port specified, so it's the default neo4j port: 7687
        port = 7687
    else:
        port = arr[1]

    return {
        net.TARGET_HOST: arr[0],
        net.TARGET_PORT: int(port),
        db.USER:         kwargs['auth'][0]
    }

def _driver(func, instance, args, kwargs):
    dsn = parse_neo4j_dsn(args, kwargs)
    Pin(service=SERVICE, app=SERVICE, app_type="db", tags=dsn).onto(Session)

    return func(*args, **kwargs)

def _run(func, instance, args, kwargs):
    pin = Pin.get_from(instance)
    if not pin or not pin.enabled():
        return func(*args, **kwargs)

    span = pin.tracer.trace("neo4j.query", service=pin.service)

    # Don't instrument if the trace is not sampled
    if not span.sampled:
        return func(*args, **kwargs)

    span.resource  = args[0]
    # NOTE: Datadog doesn't natively support a neo4j span type,
    #       so we get a 'Non-parsable SQL query' message when
    #       we hover over the span in DD's trace dashboard
    span.span_type = sql.TYPE
    span.set_tags(pin.tags)

    try:
        result = func(*args, **kwargs)
    except Exception as e:
      span.set_traceback()
      raise e
    finally:
        ddsyslogger.finish(span)

    return result