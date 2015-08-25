#!/usr/bin/env python
from __future__ import absolute_import, division, unicode_literals, print_function

from elasticsearch import Elasticsearch
import json
import os


"""
Access all the internal kibana objects, like dashboards,
visualizations, saved searches, and config as json.

import-pkg:
    -for each element in { 'docs': [] } do import

import:
    - loads json files into the internal kibana index
    - requires an additional command line argument of what file to read
    - requires the json to specify a _index, _id, and _type;
          with the actual document in _source

export-pkg:
    -{ 'docs': [<all found objects>] }

export:
    - search the internal kibana index for a specific type of document
         * 'all' or no additional CLA means all object types
         * 'config' means only the config document
         * <any ID of a dashboard> means only that dashboard and its visualizations/saved searches
    - write each found document to a separate json file
    - the document will appear in _source; with additional metadata needed
          to import it later in _index, _id, and _type.


This script makes requests (via ES API) for each object type specified.
Alternative is to skip the ES API and use urllib/curl on
    http://127.0.0.1:9200/.kibana/_search, json.loads the contents,
    and interact with the dict from there.
"""


class KibanaManager():
    def __init__(self, index, host):
        self._host_ip = host[0]
        self._host_port = host[1]
        self.index = index
        self.es = None
        self.max_hits = 9999

    @property
    def host(self):
        return (self._host_ip, self._host_port)

    @host.setter
    def host_setter(self, host):
        self._host_ip = host[0]
        self._host_port = host[1]

    def connect_es(self):
        if self.es is not None:
            return
        # use port=PORT for remote host
        self.es = Elasticsearch([{'host': self._host_ip, 'port': self._host_port}])

    def read_object_from_file(self, filename):
        print("Reading object from file: " + filename)
        obj = {}
        with open(filename, 'r') as f:
            obj = json.loads(f.read())
        return obj

    def read_pkg_from_file(self, filename):
        obj = {}
        with open(filename, 'r') as f:
            obj = json.loads(f.read())
        objs = obj['docs']
        return objs

    def put_object(self, obj):
        # TODO consider putting into a ES class
        print('put_obj: %s' % self.json_dumps(obj))
        """
        Wrapper for es.index, determines metadata needed to index from obj itself.
        If you have a raw object json string you can hard code these:
        index is .kibana (as of kibana4);
        id can be A-Za-z0-9\- and must be unique;
        doc_type is either visualization, dashboard, search
            or for settings docs: config, or index-pattern.
        """
        if obj['_index'] is None or obj['_index'] == "":
            raise Exception("Invalid Object, no index")
        if obj['_id'] is None or obj['_id'] == "":
            raise Exception("Invalid Object, no _id")
        if obj['_type'] is None or obj['_type'] == "":
            raise Exception("Invalid Object, no _type")
        if obj['_source'] is None or obj['_source'] == "":
            raise Exception("Invalid Object, no _source")
        self.connect_es()
        self.es.indices.create(index=obj['_index'], ignore=400)
        resp = self.es.index(index=obj['_index'],
                             id=obj['_id'],
                             doc_type=obj['_type'],
                             body=obj['_source'])
        return resp

    def put_pkg(self, objs):
        for obj in objs:
            self.put_object(obj)

    def put_objects(self, objects):
        for name, obj in objects.iteritems():
            self.put_object(obj)

    def del_object(self, obj):
        """
        Debug used to delete the obj of type with id of obj['_id']
        """
        if obj['_index'] is None or obj['_index'] == "":
            raise Exception("Invalid Object")
        if obj['_id'] is None or obj['_id'] == "":
            raise Exception("Invalid Object")
        if obj['_type'] is None or obj['_type'] == "":
            raise Exception("Invalid Object")
        self.connect_es()
        self.es.delete(index=obj['_index'], id=obj['_id'], doc_type=obj['_type'])

    def del_objects(self, objects):
        for name, obj in objects.iteritems():
            self.del_object(obj)

    def json_dumps(self, obj):
        return json.dumps(obj, sort_keys=True, indent=4, separators=(',', ': '))

    def write_object_to_file(self, obj, path='.'):
        """
        The objs are dicts, so convert(ordered) to json string and write to file
        """
        output = self.json_dumps(obj) + '\n'
        filename = "%s-%s.json" % (obj['_type'], obj['_id'])
        filename = os.path.join(path, filename)
        print("Writing to file: " + filename)
        with open(filename, 'w') as f:
            f.write(output)
        # print("Contents: " + output)
        return filename

    def write_objects_to_file(self, objects, path='.'):
        for name, obj in objects.iteritems():
            self.write_object_to_file(obj, path)

    def write_pkg_to_file(self, name, objects, path='.'):
        objs = {}
        objs['docs'] = []
        for _, obj in objects.iteritems():
            objs['docs'].append(obj)
        output = self.json_dumps(objs) + '\n'
        filename = "%s-Pkg.json" % (name)
        filename = os.path.join(path, filename)
        print("Writing to file: " + filename)
        with open(filename, 'w') as f:
            f.write(output)
        # print("Contents: " + output)
        return filename

    def get_objects(self, search_field, search_val):
        """
        Return all the objects of type (assuming we have less than MAX_HITS)
        from index (probably .kibana)
        """
        query = ("{ size: " + str(self.max_hits) + ", " +
                 "query: { filtered: { filter: { " +
                 search_field + ": { value: \"" + search_val + "\"" +
                 " } } } } } }")
        self.connect_es()
        res = self.es.search(index=self.index, body=query)
        # print("%d Hits:" % res['hits']['total'])
        objects = {}
        for doc in res['hits']['hits']:
            objects[doc['_id']] = {}
            # To make uploading easier in the future:
            # Record all those bits into the backup.
            # Mimics how ES returns the result.
            # Prevents having to store this in some external, contrived, format
            objects[doc['_id']]['_index'] = self.index  # also in doc['_index']
            objects[doc['_id']]['_type'] = doc['_type']
            objects[doc['_id']]['_id'] = doc['_id']
            objects[doc['_id']]['_source'] = doc['_source']  # the actual result
        return objects

    def get_config(self):
        """ Wrapper for get_objects to collect config
            NOTE, skips index-pattern
        """
        return self.get_objects("type", "config")

    def get_visualizations(self):
        """ Wrapper for get_objects to collect all visualizations """
        return self.get_objects("type", "visualization")

    def get_dashboards(self):
        """ Wrapper for get_objects to collect all dashboards """
        return self.get_objects("type", "dashboard")

    def get_searches(self):
        """ Wrapper for get_objects to collect all saved searches """
        return self.get_objects("type", "search")

    def get_dashboard_full(self, dboard):
        objects = {}
        dashboards = self.get_objects("type", "dashboard")
        vizs = self.get_objects("type", "visualization")
        searches = self.get_objects("type", "search")
        for name, val in dashboards.iteritems():
            if name == dboard:
                print("Found dashboard: " + name)
                objects[name] = val
                panels = json.loads(dashboards[name]['_source']['panelsJSON'])
                for panel in panels:
                    try:
                        for vname, vval in vizs.iteritems():
                            if vname == panel['id']:
                                print("Found vis:       " + panel['id'])
                                objects[vname] = vval
                        for sname, sval in searches.iteritems():
                            if sname == panel['id']:
                                print("Found search:    " + panel['id'])
                                objects[sname] = sval
                    except KeyError:
                        print("KeyError: %s" % panel)
                        return {}
                return objects

# end manager.py