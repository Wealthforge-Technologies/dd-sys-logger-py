# dd-sys-logger-py

`ddsyslogger` is WealthForge's wrapper around python packages that don't work out of the box when sending syslog messages to a Datadog agent via UDP.

NOTE: this package is specific to WealthForge's json log structure.

## Installation
currently, this package is not published on PyPi.  so, just install from github via pip

```
     pip install git+https://github.com/Wealthforge-Technologies/dd-sys-logger-py.git
```

## Basics
From within an application, wire up the logger thusly

```python
     import ddsyslogger

     json_handler = ddsyslogger.SysLogHandler(address = (<syslog host address>, <syslog port>)),
     facility     = ddsyslogger.SysLogHandler.LOG_LOCAL0)
     json_handler.setFormatter(ddsyslogger.JsonFormatter(<logging_environment>))

     logger = logging.getLogger(ddsyslogger.LOGGER_NAME)
     logger.addHandler(json_handler)
     logger.setLevel(logging.INFO)

     logger.info('fun')
```

The wrapper also supports logging Datadog's implementation of open tracing spans

```
     span = opentracing.tracer.start_span('lambda.invoke')
     ... stuff ...
     ddsyslogger.finish(span)
```

To ensure span errors are logged with the appropriate level

```
     try:
        ... stuff ...
     except Exception as e:
        span._dd_span.set_traceback()
     finally:
        ddsyslogger.finish(span)
```

This package also contains the following orthagonal features

Datadog Tracer for Neo4j graph database driver

```
     import ddtracerneo4j
     ddtracerneo4j.patch()
```