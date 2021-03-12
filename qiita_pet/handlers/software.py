# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------
from tornado.gen import coroutine

from qiita_core.util import execute_as_transaction
from qiita_db.software import Software, DefaultWorkflow
from .base_handlers import BaseHandler
from copy import deepcopy


class SoftwareHandler(BaseHandler):
    @coroutine
    @execute_as_transaction
    def get(self):
        # active True will only show active software
        active = True
        user = self.current_user
        if user is not None and user.level in {'admin', 'dev'}:
            active = False

        software = Software.iter(active=active)
        self.render("software.html", software=software)


class WorkflowsHandler(BaseHandler):

    def _default_parameters_parsing(self, dp):
        cmd = dp.command
        cmd_name = 'params_%d' % dp.id
        rp = deepcopy(cmd.required_parameters)
        op = deepcopy(cmd.optional_parameters)
        params = dict()
        for param, value in dp.values.items():
            if param in rp:
                del rp[param]
            if param in op:
                del op[param]
            params[param] = str(value)

        inputs = []
        outputs = []
        for input in rp.values():
            accepted_values = ' | '.join(input[1])
            # {'input_data': ('input_type', [accepted_values])}
            inputs.append([cmd.id, accepted_values])
        for output in cmd.outputs:
            outputs.append([cmd.id, ' | '.join(output)])

        return [cmd_name, cmd.id, cmd.name, dp.name, params], inputs, outputs

    @coroutine
    @execute_as_transaction
    def get(self):
        # active True will only show active workflows
        active = True
        user = self.current_user
        if user is not None and user.level in {'admin', 'dev'}:
            active = False

        workflows = []
        for w in DefaultWorkflow.iter(active=active):
            # getting the main default parameters
            nodes = []
            edges = []

            # first get edges as this will give us the main connected commands
            # and their order
            main_nodes = dict()
            graph = w.graph
            inputs = dict()
            for x, y in graph.edges:
                gconnections = graph[x][y]['connections']
                connections = ["%s | %s" % (n, at)
                               for n, _, at in gconnections.connections]

                vals_x, input_x, output_x = self._default_parameters_parsing(
                    x.default_parameter)
                vals_y, input_y, output_y = self._default_parameters_parsing(
                    y.default_parameter)
                # to make sure that commands are actually unique, we need to
                # use "fullnames", which means x_y for x and y_x for y
                name_x = '%s_%s' % (vals_x[0], vals_y[0])
                name_y = '%s_%s' % (vals_y[0], vals_x[0])
                vals_x[0] = name_x
                vals_y[0] = name_y

                if vals_x not in (nodes):
                    nodes.append(vals_x)
                    main_nodes[name_x] = dict()
                    for a, b in input_x:
                        name = 'input_%s_%s' % (name_x, b)
                        if b in inputs:
                            name = inputs[b]
                        else:
                            name = 'input_%s_%s' % (name_x, b)
                        vals = [name, a, b]
                        if vals not in nodes:
                            inputs[b] = name
                            nodes.append(vals)
                        edges.append([name, vals_x[0]])
                    for a, b in output_x:
                        name = 'output_%s_%s' % (name_x, b)
                        vals = [name, a, b]
                        if vals not in nodes:
                            nodes.append(vals)
                        edges.append([name_x, name])
                        main_nodes[name_x][b] = name

                if vals_y not in (nodes):
                    nodes.append(vals_y)
                    main_nodes[name_y] = dict()
                for a, b in input_y:
                    # checking if there is an overlap between the parameter
                    # and the connections; if there is, use the connection
                    overlap = set(main_nodes[name_x]) & set(connections)
                    if overlap:
                        # use the first hit
                        b = list(overlap)[0]

                    if b in main_nodes[name_x]:
                        name = main_nodes[name_x][b]
                    else:
                        name = 'input_%s_%s' % (name_y, b)
                        vals = [name, a, b]
                        if vals not in nodes:
                            nodes.append(vals)
                    edges.append([name, name_y])
                for a, b in output_y:
                    name = 'output_%s_%s' % (name_y, b)
                    vals = [name, a, b]
                    if vals not in nodes:
                        nodes.append(vals)
                    edges.append([name_y, name])
                    main_nodes[name_y][b] = name

            workflows.append(
                {'name': w.name, 'id': w.id, 'data_types': w.data_type,
                 'description': w.description,
                 'nodes': nodes, 'edges': edges})
        self.render("workflows.html", workflows=workflows)
