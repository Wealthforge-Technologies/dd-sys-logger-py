import socket, logging, logging.handlers
from pythonjsonlogger import jsonlogger

#
# Some constants...
#
LOGGER_NAME = 'wf_logger'

# helper method that
#   1) finishes an data dog open tracing span
#   2) logs the contents as json via syslog (similar to the golang logger)
def finish(span):
    span.finish()

    logger = logging.getLogger(LOGGER_NAME)
    logger.info({ 'data' : {'span': span._dd_span.to_dict()}})

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
            if type(msg) is unicode:
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
                self.socket.sendto(msg + '\n', self.address) # ensure that we suffix with a new line so it's properly ingested by data dog
            else:
                self.socket.sendall(msg)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)
