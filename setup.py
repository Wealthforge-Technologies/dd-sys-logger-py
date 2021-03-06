from setuptools import setup

setup(name='dd-sys-logger',
      version='0.7',
      description='datadog syslog wrapper library for json logging',
      url='https://github.com/Wealthforge-Technologies/dd-sys-logger-py',
      author='Obie Quelland',
      author_email='oquelland@wealthforge.com',
      license='MIT',
      packages=['ddsyslogger', 'ddtracerneo4j'],
      zip_safe=False)
