import socket, logging, logging.handlers, wrapt
from pythonjsonlogger import jsonlogger
from ddtrace          import Pin
from ddtrace.contrib  import dbapi
from ddtrace.ext      import sql

def _trace_method(self, method, resource, extra_tags, *args, **kwargs):
    pin = Pin.get_from(self)
    if not pin or not pin.enabled():
        return method(*args, **kwargs)
    service = pin.service

    s = pin.tracer.trace(self._self_datadog_name, service=service, resource=resource)
    s.span_type = sql.TYPE
    s.set_tags(pin.tags)
    s.set_tags(extra_tags)

    try:
        return method(*args, **kwargs)
    finally:
        s.set_metric("db.rowcount", self.rowcount)
        finish(s) # finish and log

def wrapped_trace_method(wrapped, instance, args, kwargs):
    return _trace_method(instance, *args, **kwargs)

wrapt.wrap_function_wrapper(dbapi.TracedCursor, '_trace_method', wrapped_trace_method)

# helper method that configures each syslogger within a json array
# EXAMPLE JSON Configuration:
'''
        [
            {"service_name": "xx.xxxxx.us-east-1.rds.amazonaws.com", "host": "10.0.0.1", "port": 10000},
            {"service_name": "neo4j",                                "host": "10.0.0.1", "port": 10001},
            {"service_name": "web-admin",                            "host": "10.0.0.1", "port": 10002, "is_primary"=true}
        ]
'''
def configure(env, log_level_name, syslogs):
    primary_logger = None

    for syslog in syslogs: # NOTE: ensure the overall logger for this service is the *LAST* logger in the logger array config
        print(syslog)

        json_handler = SysLogHandler(address = (syslog['host'], syslog['port']), facility=SysLogHandler.LOG_LOCAL0)
        json_handler.setFormatter(JsonFormatter(env))

        logger = logging.getLogger(syslog['service_name'])
        logger.addHandler(json_handler)
        logger.setLevel(logging.getLevelName(log_level_name)) # 'DEBUG', 'INFO', etc.

        if syslog.get('is_primary') and syslog['is_primary']:
            primary_logger = logger

        logger.debug("configured '{}' syslogger".format(syslog['service_name']))

    if not primary_logger:
        raise Exception('no primary sys logger specified')

    return primary_logger

# helper method that
#   1) finishes an data dog open tracing span
#   2) logs the contents as json via syslog (similar to the golang logger)
def finish(span):
    span.finish()

    try: # open trace span
        logger = logging.getLogger(span._dd_span.service)
        logger.info({ 'data' : {'span': span._dd_span.to_dict()}})
    except AttributeError: # data dog span
        logger = logging.getLogger(span.service)
        logger.info({ 'data' : {'span': span.to_dict()}})
    except Exception as e:
        raise e

# class for formatting a log message as json, which will later be sent to DataDog's logging platform via UDP
class JsonFormatter(jsonlogger.JsonFormatter):
    def __init__(self, env, **kw):
        self.env = env
        super(JsonFormatter, self).__init__(**kw)

    def add_fields(self, log_record, record, message_dict):
        super(JsonFormatter, self).add_fields(log_record, record, message_dict)
        if log_record.get('data') == None:
            log_record['data'] = {}

        log_record['data']['env'] = self.env

        if log_record.get('data').get('span',{}).get('error'):
            # if the span recorded an error, then set the log message's level accordingly
            log_record['level'] = 'error'
        elif log_record.get('level'):
            log_record['level'] = log_record['level'].lower()
        else:
            log_record['level'] = record.levelname.lower()


# Copyright 2001-2013 by Vinay Sajip. All Rights Reserved.
#
# Permission to use, copy, modify, and distribute this software and its
# documentation for any purpose and without fee is hereby granted,
# provided that the above copyright notice appear in all copies and that
# both that copyright notice and this permission notice appear in
# supporting documentation, and that the name of Vinay Sajip
# not be used in advertising or publicity pertaining to distribution
# of the software without specific, written prior permission.
# VINAY SAJIP DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE, INCLUDING
# ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL
# VINAY SAJIP BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR
# ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER
# IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
# OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""
Additional handlers for the logging package for Python. The core package is
based on PEP 282 and comments thereto in comp.lang.python.

Copyright (C) 2001-2013 Vinay Sajip. All Rights Reserved.

To use, simply 'import logging.handlers' and log away!
"""
class SysLogHandler(logging.handlers.SysLogHandler):
    def emit(self, record):
        """
        Emit a record.

        The record is formatted, and then sent to the syslog server. If
        exception information is present, it is NOT sent to the server.
        """
        try:
            msg = self.format(record) + '\000'
            """
            We need to convert record level to lowercase, maybe this will
            change in the future.
            """
            # in order to send as syslog json to DataDog, don't prefix with priority and facility
            # i.e., don't prefix with <134>
            # prio = '<%d>' % self.encodePriority(self.facility,
            #                                     self.mapPriority(record.levelname))
            # Message is a string. Convert to bytes as required by RFC 5424
            msg = msg.encode('utf-8')

            # msg = prio + msg
            if self.unixsocket:
                try:
                    self.socket.send(msg)
                except socket.error:
                    self.socket.close() # See issue 17981
                    self._connect_unixsocket(self.address)
                    self.socket.send(msg)
            elif self.socktype == socket.SOCK_DGRAM: # UDP (vs TCP)
                # Append a \n (new line) to the msg.
                msg += b'\x10'
                self.socket.sendto(msg, self.address) # ensure that we suffix with a new line so it's properly ingested by data dog
            else:
                self.socket.sendall(msg)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)