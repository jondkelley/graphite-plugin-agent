import os
from setuptools import setup
import sys

base_path = '%s/opt/graphite-plugin-agent' % os.getenv('VIRTUAL_ENV', '')
data_files = dict()
data_files[base_path] = ['LICENSE',
                         'README.rst',
                         'etc/init.d/graphite-plugin-agent.deb',
                         'etc/init.d/graphite-plugin-agent.rhel',
                         'etc/graphite-plugin-agent.cfg',
                         'apc-nrp.php']

console_scripts = ['graphite-plugin-agent=graphite_plugin_agent.agent:main']
install_requires = ['helper>=2.2.2', 'requests>=2.0.0', 'graphitesend>=0.10.0']
tests_require = []
extras_require = {'mongodb': ['pymongo'],
                  'pgbouncer': ['psycopg2'],
                  'postgresql': ['psycopg2']}

if sys.version_info < (2, 7, 0):
    install_requires.append('importlib')

setup(name='graphite_plugin_agent',
      version='1.0.0',
      description='Python based agent for collecting metrics for Graphite',
      url='https://github.com/jondkelley/graphite-plugin-agent/',
      packages=['graphite_plugin_agent', 'graphite_plugin_agent.plugins'],
      author='Jon Kelley',
      author_email='jonkelley@gmail.com',
      license='BSD',
      entry_points={'console_scripts': console_scripts},
      data_files=[(key, data_files[key]) for key in data_files.keys()],
      install_requires=install_requires,
      extras_require=extras_require,
      tests_require=tests_require,
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: BSD License',
          'Operating System :: POSIX',
          'Operating System :: POSIX :: Linux',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 2 :: Only',
          'Topic :: System :: Monitoring'])
