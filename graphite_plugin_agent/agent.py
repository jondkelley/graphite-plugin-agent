"""
Multiple Plugin Agent for the Graphite Platform

"""
import graphitesend
from graphitesend import GraphiteSendException
import helper
import importlib
import json
import logging
import os
import requests
import socket
import sys
import Queue as queue
import threading
import time
import re

from graphite_plugin_agent import __version__
from graphite_plugin_agent import plugins

LOGGER = logging.getLogger(__name__)


class GraphitePluginAgent(helper.Controller):
    """The GraphitePluginAgent class implements a agent that polls plugins
    every minute and reports the state to Graphite.

    """
    IGNORE_KEYS = ['graphite_host', 'graphite_port',
                   'poll_interval', 'wake_interval']
    MAX_METRICS_PER_REQUEST = 10000
    WAKE_INTERVAL = 60

    def __init__(self, args, operating_system):
        """Initialize the GraphitePluginAgent object.

        :param argparse.Namespace args: Command line arguments
        :param str operating_system: The operating_system name

        """
        super(GraphitePluginAgent, self).__init__(args, operating_system)
        self.derive_last_interval = dict()
        self.last_interval_start = None
        self.min_max_values = dict()
        self._wake_interval = (self.config.application.get('wake_interval') or
                               self.config.application.get('poll_interval') or
                               self.WAKE_INTERVAL)
        self.next_wake_interval = int(self._wake_interval)
        self.publish_queue = queue.Queue()
        self.threads = list()
        info = tuple([__version__] + list(self.system_platform))
        LOGGER.info('Agent v%s initialized, %s %s v%s', *info)

    def setup(self):
        """Setup the internal state for the controller class. This is invoked
        on Controller.run().

        Items requiring the configuration object should be assigned here due to
        startup order of operations.

        """
        self.last_interval_start = time.time()

    @property
    def agent_data(self):
        """Return the agent data section of the Graphite Platform data payload

        :rtype: dict

        """
        return {'host': socket.gethostname(),
                'pid': os.getpid(),
                'version': __version__}

    def poll_plugin(self, plugin_name, plugin, config):
        """Kick off a background thread to run the processing task.

        :param graphite_plugin_agent.plugins.base.Plugin plugin: The plugin
        :param dict config: The config for the plugin

        """

        if not isinstance(config, (list, tuple)):
            config = [config]

        for instance in config:
            thread = threading.Thread(target=self.thread_process,
                                      kwargs={'config': instance,
                                              'name': plugin_name,
                                              'plugin': plugin,
                                              'poll_interval':
                                                  int(self._wake_interval)})
            thread.run()
            self.threads.append(thread)

    def process(self):
        """This method is called after every sleep interval. If the intention
        is to use an IOLoop instead of sleep interval based daemon, override
        the run method.

        """
        start_time = time.time()
        self.start_plugin_polling()

        # Sleep for a second while threads are running
        while self.threads_running:
            time.sleep(1)

        self.threads = list()
        self.send_data_to_graphite()
        duration = time.time() - start_time
        self.next_wake_interval = self._wake_interval - duration
        if self.next_wake_interval < 1:
            LOGGER.warning('Poll interval took greater than %i seconds',
                           duration)
            self.next_wake_interval = int(self._wake_interval)
        LOGGER.info('Stats processed in %.2f seconds, next wake in %i seconds',
                    duration, self.next_wake_interval)

    def process_min_max_values(self, component):
        """Agent keeps track of previous values, so compute the differences for
        min/max values.

        :param dict component: The component to calc min/max values for

        """
        guid = component['guid']
        name = component['name']

        if guid not in self.min_max_values.keys():
            self.min_max_values[guid] = dict()

        if name not in self.min_max_values[guid].keys():
            self.min_max_values[guid][name] = dict()

        for metric in component['metrics']:
            min_val, max_val = self.min_max_values[guid][name].get(metric,
                                                                   (None, None))
            value = component['metrics'][metric]['total']
            if min_val is not None and min_val > value:
                min_val = value

            if max_val is None or max_val < value:
                max_val = value

            if component['metrics'][metric]['min'] is None:
                component['metrics'][metric]['min'] = min_val or value

            if component['metrics'][metric]['max'] is None:
                component['metrics'][metric]['max'] = max_val

            self.min_max_values[guid][name][metric] = min_val, max_val

    def send_data_to_graphite(self):
        metrics = 0
        components = list()
        while self.publish_queue.qsize():
            (name, data, last_values) = self.publish_queue.get()
            self.derive_last_interval[name] = last_values
            if isinstance(data, list):
                for component in data:
                    self.process_min_max_values(component)
                    components.append(component)
                    metrics += len(component['metrics'].keys())
                    if metrics >= self.MAX_METRICS_PER_REQUEST:
                        self.send_components(components, metrics)
                        components = list()
                        metrics = 0

            elif isinstance(data, dict):
                self.process_min_max_values(data)
                components.append(data)
                metrics += len(data['metrics'].keys())
                if metrics >= self.MAX_METRICS_PER_REQUEST:
                    self.send_components(components, metrics)
                    components = list()
                    metrics = 0

        LOGGER.debug('Done, will send remainder of %i metrics', metrics)
        self.send_components(components, metrics)

    def graphite_send(self, name, value, guid, suffix,
                        host_name, component_name="default"):
        """
        call Graphite platform using graphitesend
        """
        # replace fqdn with underscores
        host_name = re.sub(r"\.", "_", host_name)
        host_name = self.config.get('localhost_name', host_name)
        suffix = "_{0}".format(suffix)
        prefix = "graphite_agent.{0}.{1}".format(host_name, guid)
        timeout = self.config.get('graphite_timeout', 2)
        g = graphitesend.init(prefix=prefix, suffix=suffix,
            graphite_server=self.config.application['graphite_host'],
            graphite_port=self.config.application['graphite_port'],
            system_name=component_name, timeout_in_seconds=timeout)
        g.send(name, value)

    def send_components(self, components, metrics):
        """Create the headers and payload to send to Graphite platform using
        the graphitesend library
        """
        if not metrics:
            LOGGER.warning('No metrics to send to Graphite this interval')
            return

        LOGGER.info('Sending %i metrics to Graphite', metrics)
        body = {'agent': self.agent_data, 'components': components}
        LOGGER.debug(body)

        for component in components:
            host_name = self.agent_data['host']
            component_name = component['name']
            # filter NewRelic stuff away
            guid = component['guid']
            if "newrelic" in guid:
                guid = re.sub(r"^com\.(.*)\.newrelic_", "", guid)

            metrics = component['metrics']
            host = component['name']
            for metric in metrics:
                objects = {}
                objects['total'] = metrics[metric]['total']
                objects['max'] = metrics[metric]['max']
                objects['min'] = metrics[metric]['min']
                objects['count'] = metrics[metric]['count']
                # filter NewRelic stuff away
                metric = re.sub(r"[\[/]", ".", metric) # match [ or /
                metric = re.sub(r"\]", "", metric) # remove ]
                metric = re.sub(r"^Component\.", "", metric) # wipe component
                for suffix in objects:
                    try:
                        self.graphite_send(metric, objects[suffix], guid,
                            suffix, host_name, component_name)
                    except GraphiteSendException as error:
                        LOGGER.error('Graphite error: %s', error)

    @staticmethod
    def _get_plugin(plugin_path):
        """Given a qualified class name (eg. foo.bar.Foo), return the class

        :rtype: object

        """
        try:
            package, class_name = plugin_path.rsplit('.', 1)
        except ValueError:
            return None

        try:
            module_handle = importlib.import_module(package)
            class_handle = getattr(module_handle, class_name)
            return class_handle
        except ImportError:
            LOGGER.exception('Attempting to import %s', plugin_path)
            return None

    def start_plugin_polling(self):
        """Iterate through each plugin and start the polling process."""
        for plugin in [key for key in self.config.application.keys()
                       if key not in self.IGNORE_KEYS]:
            LOGGER.info('Enabling plugin: %s', plugin)
            plugin_class = None

            # If plugin is part of the core agent plugin list
            if plugin in plugins.available:
                plugin_class = self._get_plugin(plugins.available[plugin])

            # If plugin is in config and a qualified class name
            elif '.' in plugin:
                plugin_class = self._get_plugin(plugin)

            # If plugin class could not be imported
            if not plugin_class:
                LOGGER.error('Enabled plugin %s not available', plugin)
                continue

            self.poll_plugin(plugin, plugin_class,
                             self.config.application.get(plugin))

    @property
    def threads_running(self):
        """Return True if any of the child threads are alive

        :rtype: bool

        """
        for thread in self.threads:
            if thread.is_alive():
                return True
        return False

    def thread_process(self, name, plugin, config, poll_interval):
        """Created a thread process for the given name, plugin class,
        config and poll interval. Process is added to a Queue object which
        used to maintain the stack of running plugins.

        :param str name: The name of the plugin
        :param graphite_plugin_agent.plugin.Plugin plugin: The plugin class
        :param dict config: The plugin configuration
        :param int poll_interval: How often the plugin is invoked

        """
        instance_name = "%s:%s" % (name, config.get('name', 'unnamed'))
        obj = plugin(config, poll_interval,
                     self.derive_last_interval.get(instance_name))
        obj.poll()
        self.publish_queue.put((instance_name, obj.values(),
                                obj.derive_last_interval))

    @property
    def wake_interval(self):
        """Return the wake interval in seconds as the number of seconds
        until the next minute.

        :rtype: int

        """
        return self.next_wake_interval


def main():
    helper.parser.description('The Graphite Plugin Agent polls various '
                              'services and sends the data to the Graphite '
                              'Platform')
    helper.parser.name('graphite_plugin_agent')
    argparse = helper.parser.get()
    argparse.add_argument('-C',
                          action='store_true',
                          dest='configure',
                          help='Run interactive configuration')
    args = helper.parser.parse()
    if args.configure:
        print('Configuration')
        sys.exit(0)
    helper.start(GraphitePluginAgent)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
